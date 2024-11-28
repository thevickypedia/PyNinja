import json
import re
import subprocess


def size_it(input_string):
    match = re.search(r"\((\d+) Bytes\)", input_string)
    if match:
        return int(match.group(1))


def update_mountpoints(disks, device_ids):
    for disk in disks:
        if disk.get("Mount Point"):
            if disk.get("Part of Whole") in device_ids.keys():
                device_ids[disk["Part of Whole"]].append(disk.get("Mount Point"))
            for device_id in device_ids:
                if disk.get("APFS Physical Store", "").startswith(device_id):
                    device_ids[device_id].append(disk.get("Mount Point"))
    return device_ids


def diskutil_all():
    result = subprocess.run(
        "diskutil info -all", shell=True, capture_output=True, text=True
    )
    disks = []
    data_dict = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line == "**********":
            disks.append(data_dict)
            data_dict = {}
        else:
            key, value = line.split(":", 1)
            data_dict[key.strip()] = value.strip()
    data = []
    device_ids = {}
    for disk in disks:
        if disk.get("Virtual") == "No":
            new_dict = {
                **{
                    "Name": disk["Device / Media Name"],
                    "Size": size_it(disk["Disk Size"]),
                    "DeviceID": disk["Device Identifier"],
                    "Node": disk["Device Node"],
                },
            }
            data.append(new_dict)
            device_ids[disk["Device Identifier"]] = []
    mountpoints = update_mountpoints(disks, device_ids)
    for device in data:
        device["Mountpoints"] = mountpoints[device["DeviceID"]]
    return data


if __name__ == "__main__":
    dump = diskutil_all()
    print(json.dumps(dump, indent=2))
