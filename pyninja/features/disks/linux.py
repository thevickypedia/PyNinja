import json
import subprocess
from typing import Dict, List

from pydantic import FilePath


def drive_info(lib_path: FilePath) -> List[Dict[str, str]]:
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
