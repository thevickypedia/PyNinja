import asyncio
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import time
from collections.abc import Generator
from datetime import timedelta
from typing import Any, Dict, List

import psutil

from pyninja.executors import squire
from pyninja.features import operations
from pyninja.modules import cache, enums, models

LOGGER = logging.getLogger("uvicorn.default")


def landing_page() -> Dict[str, Any]:
    """Returns the landing page context for monitor endpoint.

    Returns:
        Dict[str, Any]:
        Returns a key-value pair to be inserted into the Jinja template.
    """
    uname = platform.uname()
    sys_info_basic = {
        "System": uname.system,
        "Architecture": uname.machine,
        "Node": uname.node,
        "CPU Cores": psutil.cpu_count(logical=True),
        "Uptime": squire.format_timedelta(
            timedelta(seconds=time.time() - psutil.boot_time())
        ),
    }
    if models.architecture.cpu:
        LOGGER.debug("Processor: %s", models.architecture.cpu)
        sys_info_basic["CPU"] = models.architecture.cpu
    if gpus := models.architecture.gpu:
        LOGGER.debug(gpus)
        sys_info_basic["GPU"] = ", ".join([gpu_info.get("model") for gpu_info in gpus])

    sys_info_basic["Memory"] = squire.size_converter(psutil.virtual_memory().total)
    if swap := psutil.swap_memory().total:
        sys_info_basic["Swap"] = squire.size_converter(swap)
    sys_info_network = {
        "Private IP address": squire.private_ip_address(),
        "Public IP address": squire.public_ip_address(),
    }
    return dict(
        logout="/logout",
        sys_info_basic=sys_info_basic,
        sys_info_network=sys_info_network,
        sys_info_disks=models.architecture.disks,
    )


def get_disk_info() -> Generator[Dict[str, str | int]]:
    """Get partition and usage information for each physical drive.

    Yields:
        Dict[str, str | int]:
        Yields a dictionary of key-value pairs with ID, name, and usage.
    """
    all_disks = models.architecture.disks
    for disk in all_disks:
        disk_usage: Dict[str, str | int] = {
            "name": disk.get("name"),
            "id": disk.get("device_id"),
        }
        disk_usage_totals = {"total": 0, "used": 0, "free": 0}
        if not disk.get("mountpoints") or disk.get("mountpoints") == "Not Mounted":
            continue
        mountpoints = disk.get("mountpoints", "").split(", ")
        for mountpoint in mountpoints:
            part_usage = shutil.disk_usage(mountpoint)
            for key in disk_usage_totals:
                disk_usage_totals[key] += getattr(part_usage, key)
        disk_usage.update(disk_usage_totals)
        yield disk_usage


def container_cpu_limit(container_name: str) -> int | float | None:
    """Get CPU cores configured for a particular container using NanoCpus.

    Args:
        container_name: Name of the docker container.

    Returns:
        int:
        Returns the number of CPU cores.
    """
    cmd = r"docker inspect --format '{{.HostConfig.NanoCpus}}' " + container_name
    inspector = subprocess.run(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        shell=True,
    )
    if inspector.stderr:
        LOGGER.debug(inspector.stderr.decode().strip())
        return
    if nano_cpus := inspector.stdout.decode().strip():
        return int(nano_cpus) / 1_000_000_000


def map_docker_stats(json_data: Dict[str, str]) -> Dict[str, str]:
    """Map the JSON data to a dictionary.

    Args:
        json_data: JSON data from the docker stats command.

    Returns:
        Dict[str, str]:
        Returns a dictionary with container stats.
    """
    docker_dump = {
        "Container ID": json_data.get("ID"),
        "Container Name": json_data.get("Name"),
        "CPU": json_data.get("CPUPerc"),
    }
    if cpu_limit := container_cpu_limit(json_data.get("Name")):
        if perc := re.findall(r"\d+\.\d+|\d+", json_data.get("CPUPerc")):
            docker_dump["CPU Usage"] = (
                f"{round((float(perc[0]) / 100) * cpu_limit, 2)} / {cpu_limit}"
            )
    docker_dump["Memory"] = json_data.get("MemPerc")
    docker_dump["Memory Usage"] = json_data.get("MemUsage")
    docker_dump["Block I/O"] = json_data.get("BlockIO")
    docker_dump["Network I/O"] = json_data.get("NetIO")
    return docker_dump


def get_cpu_percent(cpu_interval: int) -> List[float]:
    """Get CPU usage percentage.

    Args:
        cpu_interval: Interval to get the CPU performance.

    Returns:
        List[float]:
        Returns a list of CPU percentages.
    """
    return psutil.cpu_percent(interval=cpu_interval, percpu=True)


def containers() -> bool:
    """Check if any Docker containers are running."""
    docker_ps = subprocess.run(
        "docker ps -q",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        shell=True,
    )
    if docker_ps.stderr:
        LOGGER.debug(docker_ps.stderr.decode().strip())
        return False
    if docker_ps.stdout.decode().strip().splitlines():
        return True


async def get_docker_stats() -> List[Dict[str, str]]:
    """Run the docker stats command asynchronously and parse the output.

    Returns:
        List[Dict[str, str]]:
        Returns a list of key-value pairs with the container stat and value.
    """
    if not containers():
        return []
    process = await asyncio.create_subprocess_shell(
        'docker stats --no-stream --format "{{json .}}"',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if stderr:
        LOGGER.debug(stderr.decode().strip())
        return []
    return [
        map_docker_stats(json.loads(line))
        for line in stdout.decode().strip().splitlines()
    ]


# noinspection PyProtectedMember
async def get_system_metrics() -> Dict[str, dict]:
    """Async handler for virtual memory, swap memory disk usage and CPU load averages.

    Returns:
        Dict[str, dict]:
        Returns a nested dictionary.
    """
    try:
        m1, m5, m15 = os.getloadavg() or (None, None, None)
    except AttributeError:
        m1, m5, m15 = psutil.getloadavg() or (None, None, None)
    return dict(
        memory_info=psutil.virtual_memory()._asdict(),
        swap_info=psutil.swap_memory()._asdict(),
        load_averages=dict(m1=m1, m5=m5, m15=m15),
    )


def get_os_agnostic_metrics() -> Generator[Dict[str, Any]]:
    """Retrieves OS-agnostic PyUdisk metrics.

    Returns:
        Dict[str, Any]:
        Returns a dictionary of retrieved values.
    """
    from pyudisk import EnvConfig, smart_metrics, util

    rendered = {}
    for disk in smart_metrics(EnvConfig(smart_lib=models.env.smart_lib)):
        if models.OPERATING_SYSTEM == enums.OperatingSystem.linux:
            info = disk.Info
            attributes = disk.Attributes
            partition = disk.Partition
            if disk.Usage:
                rendered["usage"] = disk.Usage.model_dump()
            if info:
                rendered["model"] = info.Model
            if partition:
                rendered["mountpoint"] = partition.MountPoints
            if attributes:
                rendered["temperature"] = (
                    f"{util.kelvin_to_fahrenheit(attributes.SmartTemperature)} °F"
                    + " / "
                    + f"{util.kelvin_to_celsius(attributes.SmartTemperature)} °C"
                )
                rendered["uptime"] = squire.convert_seconds(
                    attributes.SmartPowerOnSeconds
                )
                rendered["bad_sectors"] = attributes.SmartNumBadSectors
                rendered["test_status"] = attributes.SmartSelftestStatus
                rendered["updated"] = round(time.time() - disk.Attributes.SmartUpdated)
        if models.OPERATING_SYSTEM == enums.OperatingSystem.darwin:
            rendered["model"] = disk.model_name
            rendered["mountpoint"] = [
                partition.mountpoint
                for partition in psutil.disk_partitions()
                if not partition.mountpoint.startswith("/System/Volumes")
            ]
            if disk.usage:
                rendered["usage"] = disk.usage.model_dump()
            if disk.temperature and disk.temperature.current:
                rendered["temperature"] = (
                    f"{util.celsius_to_fahrenheit(disk.temperature.current)} °F"
                    + " / "
                    + f"{disk.temperature.current} °C"
                )
            if disk.power_on_time and disk.power_on_time.hours:
                rendered["uptime"] = squire.convert_hours(disk.power_on_time.hours)
            if disk.smart_status and disk.smart_status.passed:
                rendered["test_status"] = "PASSED"
            rendered["updated"] = round(time.time() - disk.local_time.time_t) or 60
        yield rendered


@cache.timed_cache(60)
def pyudisk_metrics() -> Dict[str, str | List[dict]]:
    """Retrieves metrics from PyUdisk library.

    See Also:
        - This is a timed-cache function. Meaning: The output from this function will be cached for 60s.
        - This is to avoid gathering the metrics every 2s, to improve latency and avoid extra overhead.

    Returns:
        List[Dict[str, int | str | float]]:
        List of required metrics as a dictionary of key-value pairs.
    """
    pyudisk_stats = []
    metric = None
    for metric in get_os_agnostic_metrics():
        pyudisk_stats.append(
            {
                **{
                    "Model": metric.get("model", "N/A"),
                    "Mountpoint": metric.get("mountpoint", "N/A"),
                    "Temperature": metric.get("temperature", "N/A"),
                    "Bad Sectors": metric.get("bad_sectors", "N/A"),
                    "Test Status": metric.get("test_status", "N/A"),
                    "Uptime": metric.get("uptime", "N/A"),
                },
                **metric.get("usage", {}),
            }
        )
    # Smart metrics are gathered at certain system intervals - so no need to get this attr from all the drives
    updated = metric.get("updated", 0)
    return {
        "pyudisk_updated": (
            f"{squire.convert_seconds(updated, 1)} ago"
            if updated >= 100
            else f"{updated} seconds ago"
        ),
        "pyudisk_stats": pyudisk_stats,
    }


async def system_resources() -> Dict[str, dict | List[Dict[str, str | int]]]:
    """Gather system resources including Docker stats asynchronously.

    Returns:
        Dict[str, dict]:
        Returns a nested dictionary.
    """
    system_metrics_task = asyncio.create_task(get_system_metrics())
    docker_stats_task = asyncio.create_task(get_docker_stats())
    service_stats_task = asyncio.create_task(
        operations.service_monitor(models.env.services)
    )
    process_stats_task = asyncio.create_task(
        operations.process_monitor(models.env.processes)
    )

    # CPU percent check is a blocking call and cannot be awaited, so run it in a separate thread
    loop = asyncio.get_event_loop()
    cpu_usage_task = loop.run_in_executor(
        models.EXECUTOR, get_cpu_percent, *(models.MINIMUM_CPU_UPDATE_INTERVAL,)
    )

    system_metrics = await system_metrics_task
    docker_stats = await docker_stats_task
    service_stats = await service_stats_task
    process_stats = await process_stats_task
    cpu_usage = await cpu_usage_task
    if models.OPERATING_SYSTEM in (
        enums.OperatingSystem.linux,
        enums.OperatingSystem.darwin,
    ):
        try:
            system_metrics.update(pyudisk_metrics())
        except ModuleNotFoundError:
            # Expected if module is not installed
            pass
        except Exception as warn:
            LOGGER.warning(warn)

    system_metrics["cpu_usage"] = cpu_usage
    system_metrics["docker_stats"] = docker_stats
    system_metrics["service_stats"] = service_stats
    system_metrics["process_stats"] = process_stats
    return system_metrics
