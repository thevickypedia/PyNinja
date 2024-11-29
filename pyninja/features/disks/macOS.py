import logging
import re
import subprocess
from collections import defaultdict
from typing import Dict, List

from pyninja.executors import squire
from pyninja.modules import models

LOGGER = logging.getLogger("uvicorn.default")


def parse_size(input_string: str) -> int:
    """Extracts size in bytes from a string.

    Args:
        input_string: Input string from diskutil output.

    Returns:
        int:
        Returns the size in bytes as an integer.
    """
    match = re.search(r"\((\d+) Bytes\)", input_string)
    return int(match.group(1)) if match else 0


def update_mountpoints(
    disks: List[Dict[str, str]], device_ids: defaultdict
) -> defaultdict:
    """Updates mount points for physical devices based on diskutil data.

    Args:
        disks: All disk info data as list.
        device_ids: Device IDs as default dict.

    Returns:
        defaultdict:
        Returns a defaultdict object with updated mountpoints as list.
    """
    for disk in disks:
        part_of_whole = disk.get("Part of Whole")
        apfs_store = disk.get("APFS Physical Store", "")
        mount_point = disk.get("Mount Point")
        read_only = "Yes" in disk.get("Volume Read-Only")
        if mount_point and not mount_point.startswith("/System/Volumes/"):
            if part_of_whole in device_ids:
                device_ids[part_of_whole].append(mount_point)
            else:
                for device_id in device_ids:
                    if apfs_store.startswith(device_id) and read_only:
                        device_ids[device_id].append(mount_point)
    for device_id, mountpoints in device_ids.items():
        if not mountpoints:
            device_ids[device_id] = ["Not Mounted"]
    return device_ids


def parse_diskutil_output(stdout: str) -> List[Dict[str, str]]:
    """Parses `diskutil info -all` output into structured data.

    Args:
        stdout: Standard output from diskutil command.

    Returns:
        List[Dict[str, str]]:
        Returns a list of dictionaries with parsed drives' data.
    """
    disks = []
    disk_info = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line == "**********":
            disks.append(disk_info)
            disk_info = {}
        else:
            key, value = map(str.strip, line.split(":", 1))
            disk_info[key] = value
    return disks


def drive_info() -> List[Dict[str, str]]:
    """Get disks attached to macOS devices.

    Returns:
        List[Dict[str, str]]:
        Returns disks information for macOS devices.
    """
    result = subprocess.run(
        [models.env.disk_lib, "info", "-all"], capture_output=True, text=True
    )
    disks = parse_diskutil_output(result.stdout)
    device_ids = defaultdict(list)
    physical_disks = []
    for disk in disks:
        if disk.get("Virtual") == "No":
            physical_disks.append(
                {
                    "Name": disk.get("Device / Media Name"),
                    "Size": squire.size_converter(
                        parse_size(disk.get("Disk Size", ""))
                    ),
                    "DeviceID": disk.get("Device Identifier"),
                    "Node": disk.get("Device Node"),
                }
            )
            # Instantiate default dict with keys as DeviceIDs and values as empty list
            _ = device_ids[disk["Device Identifier"]]
    mountpoints = update_mountpoints(disks, device_ids)
    for disk in physical_disks:
        disk["Mountpoints"] = ", ".join(mountpoints[disk["DeviceID"]])
    return physical_disks
