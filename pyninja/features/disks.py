import json
import logging
import re
import subprocess
from typing import Dict, List

import psutil
from pydantic import FilePath

from pyninja.executors import squire
from pyninja.modules import enums, models

LOGGER = logging.getLogger("uvicorn.default")


def get_partitions_for_disk(device_id: str) -> List[str]:
    """Use psutil to find partitions for a given device.

    Args:
        device_id:

    Returns:
        List[str]:
        Returns the list of partitions in a disk.
    """
    if not device_id.startswith("/dev/"):
        device_id = f"/dev/{device_id}"
    return [
        p.device
        for p in psutil.disk_partitions(all=True)
        if p.device.startswith(device_id)
    ] or [0]


def parse_size(size_str: str) -> str:
    """Convert size string with units to a standard size in bytes.

    Args:
        size_str: Size with unit as string.

    Returns:
        str:
        Returns the parsed size as string with units attached.
    """
    # Define regex to capture the numeric part and the unit part
    match = re.match(r"([\d.]+)([KMGTP]?)", size_str.strip())
    if match:
        value, unit = match.groups()
        value = float(value)
        # Map units to their byte multipliers (base-2)
        unit_multipliers = {
            "K": 2**10,  # Kilobytes
            "M": 2**20,  # Megabytes
            "G": 2**30,  # Gigabytes
            "T": 2**40,  # Terabytes
            "P": 2**50,  # Petabytes
        }
        # Convert size to bytes
        multiplier = unit_multipliers.get(unit, 1)  # Default to bytes if no unit
        return squire.size_converter(value * multiplier)
    return (
        size_str.replace("K", " KB")
        .replace("M", " MB")
        .replace("G", " GB")
        .replace("T", " TB")
        .replace("P", " PB")
    )


def _linux(lib_path: FilePath) -> List[Dict[str, str]]:
    """Get disks attached to Linux devices.

    Args:
        lib_path: Returns the library path for disk information.

    Returns:
        List[Dict[str, str]]:
        Returns disks information for Linux distros.
    """
    # Using -d to list only physical disks, and filtering out loop devices
    result = subprocess.run(
        [lib_path, "-o", "NAME,SIZE,TYPE,MODEL,MOUNTPOINT", "-J"],
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    disks = []
    for device in data.get("blockdevices", []):
        if device["type"] == "disk":
            disk_info = {
                "DeviceID": device["name"],
                "Size": device["size"],
                "Name": device.get("model", "Unknown"),
                "Mountpoints": [],
            }
            # Collect mount points from partitions
            if "children" in device:
                for partition in device["children"]:
                    if partition.get("mountpoint"):
                        disk_info["Mountpoints"].append(partition["mountpoint"])
            disk_info["Mountpoints"] = ", ".join(disk_info["Mountpoints"])
            disks.append(disk_info)
    return disks


def is_physical_disk(info_lines: List[str]) -> bool:
    """Check if the disk is a physical disk using diskutil info.

    Args:
        info_lines: Disk information split by lines.

    Returns:
        bool:
        Boolean to indicate virtual or physical
    """
    for line in info_lines:
        if "Virtual" in line and "Yes" in line:
            return False
    return True


def _darwin(lib_path: FilePath) -> List[Dict[str, str]]:
    """Get disks attached to macOS devices.

    Args:
        lib_path: Returns the library path for disk information.

    Returns:
        List[Dict[str, str]]:
        Returns disks information for macOS devices.
    """
    result = subprocess.run([lib_path, "list"], capture_output=True, text=True)
    disks = result.stdout.strip().splitlines()
    # Extract the lines that represent physical disks (e.g., /dev/disk0)
    disk_lines = [line for line in disks if line.startswith("/dev/disk")]
    disk_info = []
    for line in disk_lines:
        device_id = line.split()[0]  # /dev/diskX
        # Use diskutil info to get more information about the disk
        disk_info_result = subprocess.run(
            [lib_path, "info", device_id],
            capture_output=True,
            text=True,
        )
        info_lines = disk_info_result.stdout.strip().splitlines()
        # Skip virtual disks
        if not is_physical_disk(info_lines):
            continue
        # Extract the relevant info (Name, Size, etc.)
        disk_data = {}
        for info_line in info_lines:
            if "Device / Media Name:" in info_line:
                disk_data["Name"] = info_line.split(":")[1].strip()
            if "Disk Size:" in info_line:
                # Extract size and unit (e.g., 500.11 GB)
                size_info = info_line.split(":")[1].split("(")[0].strip()
                disk_data["Size"] = size_info
        # Add DeviceID and Partitions (placeholder)
        disk_data["DeviceID"] = device_id
        disk_data["Partitions"] = len(get_partitions_for_disk(device_id))
        disk_info.append(disk_data)
    return disk_info


def _reformat_windows(data: Dict[str, str | int | float]) -> Dict[str, str]:
    """Reformats each drive's information for Windows OS.

    Args:
        data: Data as a dictionary.

    Returns:
        Dict[str, str]:
        Returns a dictionary of key-value pairs.
    """
    data["Size"] = squire.size_converter(data["Size"])
    data["Name"] = data["Model"]
    del data["Caption"]
    del data["Model"]
    return data


# Windows specific method using wmic
def _windows(lib_path: FilePath) -> List[Dict[str, str]]:
    """Get disks attached to Windows devices.

    Args:
        lib_path: Returns the library path for disk information.

    Returns:
        List[Dict[str, str]]:
        Returns disks information for Windows machines.
    """
    ps_command = "Get-CimInstance Win32_DiskDrive | Select-Object Caption, DeviceID, Model, Partitions, Size | ConvertTo-Json"  # noqa: E501
    result = subprocess.run(
        [lib_path, "-Command", ps_command], capture_output=True, text=True
    )
    disks_info = json.loads(result.stdout)
    if isinstance(disks_info, list):
        return [_reformat_windows(info) for info in disks_info]
    return [_reformat_windows(disks_info)]


def get_all_disks() -> List[Dict[str, str]]:
    """OS-agnostic function to get all disks connected to the host system."""
    os_map = {
        enums.OperatingSystem.darwin: _darwin,
        enums.OperatingSystem.linux: _linux,
        enums.OperatingSystem.windows: _windows,
    }
    try:
        return os_map[models.OPERATING_SYSTEM](models.env.disk_lib)
    except Exception as error:
        LOGGER.error(error)
