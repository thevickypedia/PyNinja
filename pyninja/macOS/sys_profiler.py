import json
import subprocess


def sys_profiler():
    result = subprocess.run(
        ["/usr/sbin/system_profiler", "SPStorageDataType", "-json"],
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    usable_volumes = []
    for volume in data["SPStorageDataType"]:
        if volume.get("writable") == "yes":
            usable_volumes.append(volume)
    for mlist in usable_volumes:
        yield {
            "DeviceID": mlist["_name"],
            "Size": mlist["size_in_bytes"],
            "Name": mlist["physical_drive"]["device_name"],
            "Mountpoints": mlist["mount_point"],
        }


if __name__ == "__main__":
    data = list(sys_profiler())
    print(json.dumps(data, indent=2))
