import json
import re
import subprocess


def size_it(input_string):
    match = re.search(r"\((\d+) Bytes\)", input_string)
    if match:
        return int(match.group(1))


def get_mountpoints(disk_node):
    result = subprocess.run(
        [f"diskutil info -plist {disk_node}"],
        shell=True,
        capture_output=True,
        text=True,
    )
    import plistlib

    if mountpoint := plistlib.loads(result.stdout.encode())["MountPoint"]:
        return mountpoint
    else:
        print("No mountpoint found!!")
        return "/"


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
    for disk in disks:
        if disk.get("Virtual") == "No":
            new_dict = {
                "Name": disk["Device / Media Name"],
                "Size": size_it(disk["Disk Size"]),
                "DeviceID": disk["Device Identifier"],
                "Node": disk["Device Node"],
                "Mountpoints": get_mountpoints(disk["Device Node"]),
            }
            new_dict["total"] = new_dict["Size"]
            data.append(new_dict)
    return data


if __name__ == "__main__":
    data = diskutil_all()
    print(json.dumps(data, indent=2))
