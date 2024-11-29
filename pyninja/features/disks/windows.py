import collections
import json
import logging
import re
import subprocess
from typing import Dict, List, Tuple

from pyninja.executors import squire
from pyninja.modules import models

LOGGER = logging.getLogger("uvicorn.default")


def reformat_windows(data: Dict[str, str | int | float]) -> Dict[str, str]:
    """Reformats each drive's information for Windows OS.

    Args:
        data: Data as a dictionary.

    Returns:
        Dict[str, str]:
        Returns a dictionary of key-value pairs.
    """
    data["ID"] = data["DeviceID"][-1]
    data["Name"] = data["Model"]
    data["DeviceID"] = data["DeviceID"].replace("\\", "").replace(".", "")
    data["Size"] = squire.size_converter(data["Size"])
    del data["Caption"]
    del data["Model"]
    return data


def get_drives() -> List[Dict[str, str]]:
    """Get physical drives connected to a Windows machine.

    Returns:
        List[Dict[str, str]]:
        Returns the formatted data for all the drives as a list of key-value pairs.
    """
    # noinspection LongLine
    ps_command = "Get-CimInstance Win32_DiskDrive | Select-Object Caption, DeviceID, Model, Partitions, Size | ConvertTo-Json"  # noqa: E501
    result = subprocess.run(
        [models.env.disk_lib, "-Command", ps_command], capture_output=True, text=True
    )
    disks_info = json.loads(result.stdout)
    if isinstance(disks_info, list):
        return [reformat_windows(info) for info in disks_info]
    return [reformat_windows(disks_info)]


def clean_ansi_escape_sequences(text: str) -> str:
    """Regular expression to remove ANSI escape sequences.

    Args:
        text: Text with ansi escape characters.

    Returns:
        str:
        Cleaned text.
    """
    ansi_escape = re.compile(r"\x1b\[[0-9;]*[mGKF]")
    return ansi_escape.sub("", text)


def get_physical_disks_and_partitions() -> List[Tuple[str, str, str]]:
    """Powershell Core command to get physical disks and their partitions with drive letters (mount points).

    Returns:
        List[Tuple[str, str, str]]:
        List of tuples with disk_number, partition_number, mount_point.
    """
    command_ps = [
        models.env.disk_lib,
        "-Command",
        """
        Get-PhysicalDisk | ForEach-Object {
            $disk = $_
            $partitions = Get-Partition -DiskNumber $disk.DeviceID
            $partitions | ForEach-Object {
                [PSCustomObject]@{
                    DiskNumber = $disk.DeviceID
                    Partition = $_.PartitionNumber
                    DriveLetter = (Get-Volume -Partition $_).DriveLetter
                    MountPoint = (Get-Volume -Partition $_).DriveLetter
                }
            }
        }
        """,
    ]

    # Run the PowerShell command using subprocess.run
    result = subprocess.run(
        command_ps, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    if result.stderr:
        LOGGER.error(result.stderr)
        return []

    # Clean the output to remove ANSI escape sequences
    cleaned_output = clean_ansi_escape_sequences(result.stdout)

    # Parse the output to get disk and partition info
    disks_and_partitions = []
    # Split the cleaned output into lines and skip header and separator lines
    lines = cleaned_output.splitlines()
    for line in lines:
        # Skip empty lines and headers (first 2 lines are headers)
        if line.startswith("DiskNumber") or line.startswith("-"):
            continue

        # Split the line into parts and extract the required info
        parts = line.split()
        if len(parts) >= 4:
            disk_number = parts[0]
            partition_number = parts[1]
            mount_point = parts[3]  # Assuming this is the drive letter (e.g., C, D)
            disks_and_partitions.append((disk_number, partition_number, mount_point))

    return disks_and_partitions


def get_disk_usage() -> Dict[str, List[str]]:
    """Get all physical disks and their partitions with mount points.

    Returns:
        Dict[str, List[str]]:
        Returns a dictionary of DeviceID as key and mount paths as value.
    """
    disks_and_partitions = get_physical_disks_and_partitions()

    if not disks_and_partitions:
        LOGGER.error("No disks or partitions found.")
        return {}

    output_data = collections.defaultdict(list)
    # Loop through the list of disks and partitions, and fetch disk usage for each mount point
    for disk_number, partition_number, mount_point in disks_and_partitions:
        # Construct the mount point path (e.g., C:\, D:\, etc.)
        mount_path = f"{mount_point}:\\"
        output_data[disk_number].append(mount_path)
    return output_data


def drive_info() -> List[Dict[str, str]]:
    """Get disks attached to Windows devices.

    Returns:
        List[Dict[str, str]]:
        Returns disks information for Windows machines.
    """
    data = get_drives()
    usage = get_disk_usage()
    for item in data:
        device_id = item["ID"]
        item.pop("ID")
        if device_id in usage:
            item["Mountpoints"] = ", ".join(usage[device_id])
        else:
            item["Mountpoints"] = "Not Mounted"
    return data
