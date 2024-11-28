import json
import logging
import re
import subprocess
import time
from collections import defaultdict

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
HANDLER = logging.StreamHandler()
DEFAULT_FORMATTER = logging.Formatter(
    datefmt="%b-%d-%Y %I:%M:%S %p",
    fmt="%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(funcName)s - %(message)s",
)
HANDLER.setFormatter(DEFAULT_FORMATTER)
LOGGER.addHandler(HANDLER)


def time_it(func):
    """Decorator to measure the execution time of a function."""

    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        LOGGER.info(f"Function '{func.__name__}' executed in {end - start:.4f} seconds.")
        return result

    return wrapper


@time_it
def parse_size(input_string):
    """Extracts size in bytes from a string like '(12345 Bytes)'."""
    match = re.search(r'\((\d+) Bytes\)', input_string)
    return int(match.group(1)) if match else None


@time_it
def update_mountpoints(disks, device_ids):
    """Updates mount points for physical devices based on diskutil data."""
    for disk in disks:
        part_of_whole = disk.get("Part of Whole")
        apfs_store = disk.get("APFS Physical Store", "")
        mount_point = disk.get("Mount Point")
        if mount_point and not mount_point.startswith("/System/Volumes/"):
            if part_of_whole in device_ids:
                device_ids[part_of_whole].append(mount_point)
            else:
                for device_id in device_ids:
                    if apfs_store.startswith(device_id):
                        device_ids[device_id].append(mount_point)
    return device_ids


@time_it
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


@time_it
def extract_raw_data() -> subprocess.CompletedProcess[str]:
    """Extract all diskutil info."""
    return subprocess.run("diskutil info -all", shell=True, capture_output=True, text=True)


def diskutil_all():
    """Fetches disk information using `diskutil info -all`."""
    result = extract_raw_data()
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
