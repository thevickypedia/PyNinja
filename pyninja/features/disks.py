import json
import logging
import subprocess
from typing import Dict, List

from pydantic import FilePath

from pyninja.executors import squire
from pyninja.modules import enums, models
from pyninja.macOS.draft import diskutil_all

LOGGER = logging.getLogger("uvicorn.default")


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


def _darwin(lib_path: FilePath) -> List[Dict[str, str]]:
    """Get disks attached to macOS devices.

    Args:
        lib_path: Returns the library path for disk information.

    Returns:
        List[Dict[str, str]]:
        Returns disks information for macOS devices.
    """
    return diskutil_all(str(lib_path))


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
