import json
import re
import subprocess
from collections import defaultdict


def parse_size(input_string):
    """Extracts size in bytes from a string like '(12345 Bytes)'."""
    match = re.search(r'\((\d+) Bytes\)', input_string)
    return int(match.group(1)) if match else 0


def update_mountpoints(disks, device_ids):
    """Updates mount points for physical devices based on diskutil data."""
    for disk in disks:
        part_of_whole = disk.get("Part of Whole")
        apfs_store = disk.get("APFS Physical Store", "")
        if mount_point := disk.get("Mount Point"):
            if part_of_whole in device_ids:
                device_ids[part_of_whole].append(mount_point)
            for device_id in device_ids:
                if apfs_store.startswith(device_id):
                    device_ids[device_id].append(mount_point)
    return device_ids


def parse_diskutil_output(output):
    """Parses `diskutil info -all` output into structured data."""
    disks = []
    disk_info = {}
    for line in output.splitlines():
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


def diskutil_all():
    """Fetches disk information using `diskutil info -all`."""
    result = subprocess.run("diskutil info -all", shell=True, capture_output=True, text=True)
    disks = parse_diskutil_output(result.stdout)
    device_ids = defaultdict(list)
    physical_disks = []
    for disk in disks:
        if disk.get("Virtual") == "No":
            physical_disks.append({
                "Name": disk.get("Device / Media Name"),
                "Size": parse_size(disk.get("Disk Size", "")),
                "DeviceID": disk.get("Device Identifier"),
                "Node": disk.get("Device Node"),
            })
            # Instantiate default dict with keys as DeviceIDs and values as empty list
            _ = device_ids[disk["Device Identifier"]]
    mountpoints = update_mountpoints(disks, device_ids)
    for disk in physical_disks:
        disk["Mountpoints"] = mountpoints[disk["DeviceID"]]
    return physical_disks


if __name__ == '__main__':
    dump = diskutil_all()
    print(json.dumps(dump, indent=2))
