import json
import subprocess
from typing import Dict, List
from pydantic import FilePath

import subprocess
import re
import collections
from pyninja.executors import squire


def _reformat_windows(data: Dict[str, str | int | float]) -> Dict[str, str]:
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


def _windows(lib_path: FilePath) -> List[Dict[str, str]]:
    """Get disks attached to Windows devices.

    Args:
        lib_path: Returns the library path for disk information.

    Returns:
        List[Dict[str, str]]:
        Returns disks information for Windows machines.
    """
    data = get_drives(lib_path)
    usage = get_disk_usage(lib_path)
    for item in data:
        device_id = item['ID']
        item.pop("ID")
        if device_id in usage:
            item['Mountpoints'] = ", ".join(usage[device_id])
    return data


def get_drives(lib_path: FilePath) -> List[Dict[str, str]]:
    ps_command = "Get-CimInstance Win32_DiskDrive | Select-Object Caption, DeviceID, Model, Partitions, Size | ConvertTo-Json"  # noqa: E501
    result = subprocess.run(
        [lib_path, "-Command", ps_command], capture_output=True, text=True
    )
    disks_info = json.loads(result.stdout)
    if isinstance(disks_info, list):
        return [_reformat_windows(info) for info in disks_info]
    return [_reformat_windows(disks_info)]

def clean_ansi_escape_sequences(text):
    # Regular expression to remove ANSI escape sequences
    ansi_escape = re.compile(r'\x1b\[[0-9;]*[mGKF]')
    return ansi_escape.sub('', text)

def get_physical_disks_and_partitions(lib_path: FilePath):
    # PowerShell Core command to get physical disks and their partitions with drive letters (mount points)
    command_ps = [
        lib_path,
        "-Command",
        '''
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
        '''
    ]
    
    # Run the PowerShell command using subprocess.run
    result = subprocess.run(command_ps, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.stderr:
        print("Error:", result.stderr)
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


def get_disk_usage(lib_path):
    # Get all physical disks and their partitions with mount points
    disks_and_partitions = get_physical_disks_and_partitions(lib_path)

    if not disks_and_partitions:
        print("No disks or partitions found.")
        return

    output_data = collections.defaultdict(list)
    # Loop through the list of disks and partitions, and fetch disk usage for each mount point
    for disk_number, partition_number, mount_point in disks_and_partitions:
        # Construct the mount point path (e.g., C:\, D:\, etc.)
        mount_path = f"{mount_point}:\\"
        output_data[disk_number].append(mount_path)
    return output_data
