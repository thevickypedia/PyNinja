import json
import subprocess
import logging
import re
import psutil
from typing import List, Dict

from pydantic import FilePath
from . import models, squire

LOGGER = logging.getLogger("uvicorn.default")


def parse_size(size_str):
    """Convert size string with units to a standard size in bytes."""
    # Define regex to capture the numeric part and the unit part
    match = re.match(r"([\d.]+)([KMGTPP]?)", size_str.strip())
    if match:
        value, unit = match.groups()
        value = float(value)
        # Map units to their byte multipliers (base-2)
        unit_multipliers = {
            'K': 2**10,    # Kilobytes
            'M': 2**20,    # Megabytes
            'G': 2**30,    # Gigabytes
            'T': 2**40,    # Terabytes
            'P': 2**50     # Petabytes
        }
        # Convert size to bytes
        multiplier = unit_multipliers.get(unit, 1)  # Default to bytes if no unit
        return value * multiplier
    return size_str\
        .replace('K', ' KB')\
        .replace('M', ' MB')\
        .replace('G', ' GB')\
        .replace('T', ' TB')\
        .replace('P', ' PB')


def _linux(lib_path: FilePath):
    """Get disks attached to Linux devices.

    Retruns:
        List[Dict[str, str]]:
        Returns disks information for Linux distros.
    """
    # Using -d to list only physical disks, and filtering out loop devices
    result = subprocess.run(
        [lib_path, "-o", "NAME,SIZE,TYPE,MODEL", "-d"],
        capture_output=True,
        text=True,
    )
    disks = result.stdout.strip().splitlines()
    filtered_disks = [disk for disk in disks if "loop" not in disk]
    keys = filtered_disks[0]\
        .lower()\
        .replace('name', 'DeviceID')\
        .replace('model', 'Name')\
        .replace('size', 'Size')\
        .split()
    disk_info = [
        dict(zip(keys, line.split(None, len(keys) - 1)))
        for line in filtered_disks[1:]
    ]
    # Normalize the output, ensuring the correct field names and types
    for disk in disk_info:
        disk['Size'] = squire.size_converter(parse_size(disk['Size']))
        partitions = [p.device for p in psutil.disk_partitions(all=True) if p.device.startswith(f"/dev/{disk['DeviceID']}")]
        disk['Partitions'] = len(partitions)
        disk.pop('type', None)
    return disk_info


def _darwin(lib_path: FilePath):
    result = subprocess.run(
        [lib_path, "list"],
        capture_output=True,
        text=True
    )
    return result.stdout


def _reformat_windows(data):
    data["Size"] = squire.size_converter(data["Size"])
    data["Name"] = data["Model"]
    del data["Caption"]
    del data["Model"]
    return data


# Windows specific method using wmic
def _windows():
    ps_command = """
    Get-CimInstance Win32_DiskDrive | Select-Object Caption, DeviceID, Model, Partitions, Size | ConvertTo-Json
    """
    result = subprocess.run(["pwsh", "-Command", ps_command], capture_output=True, text=True)
    disks_info = json.loads(result)
    if isinstance(disks_info, list):
        return [_reformat_windows(info) for info in disks_info]
    return [_reformat_windows(disks_info)]



def get_all_disks() -> List[Dict[str, str]]:
    """OS agnostic function to get all disks connected to the host system."""
    os_map = {
        "darwin": _darwin,
        "linux": _linux,
    }
    try:
        return os_map[models.OPERATING_SYSTEM](models.env.disk_lib)
    except KeyError:
        return _windows()
    except Exception as error:
        LOGGER.error(error)


# Fall back to psutil, although this gives partitions
def list_partitions_psutil():
    disks = []
    for partition in psutil.disk_partitions(all=True):
        disks.append(f"Device: {partition.device}, Mountpoint: {partition.mountpoint}")
    return "\n".join(disks)
