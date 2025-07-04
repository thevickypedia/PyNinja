import asyncio
import json
import logging
import os
import platform
import re
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
    sys_info_disks = [
        {k.replace("_", " ").title(): v for k, v in disk.items()}
        for disk in models.architecture.disks
    ]
    return dict(
        logout=enums.APIEndpoints.logout,
        sys_info_basic=sys_info_basic,
        sys_info_network=sys_info_network,
        sys_info_disks=sys_info_disks,
    )


@cache.timed_cache(30)
async def get_disk_info() -> List[Dict[str, str | int]]:
    """Get partition and usage information for each physical drive.

    Returns:
        List[Dict[str, str | int]]:
        Returns a list of key-value pairs with ID, name, and usage.
    """
    usage_metrics = []
    for disk in models.architecture.disks:
        disk_usage: Dict[str, str | int] = {
            "name": disk.get("name"),
            "id": disk.get("device_id"),
        }
        if not disk.get("mountpoints"):
            continue
        disk_usage.update(
            squire.total_mountpoints_usage(disk["mountpoints"], as_bytes=True)
        )
        usage_metrics.append(disk_usage)
    return usage_metrics


def container_cpu_limit(container_id: str) -> int | float | None:
    """Get CPU cores configured for a particular container using NanoCpus.

    Args:
        container_id: ID of the Docker container to inspect.

    Returns:
        int:
        Returns the number of CPU cores.
    """
    cmd = r"docker inspect --format '{{.HostConfig.NanoCpus}}' " + container_id
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


def floater(value: float) -> int | float:
    """Convert a float to an int if it is a whole number, otherwise return the float.

    Args:
        value: Value to convert.

    Returns:
        int | float:
        Returns an int if the value is a whole number, otherwise returns the float.
    """
    if value == 0.0:
        return 0
    if "." in str(value):
        return value
    return int(value)


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
    if cpu_percent := re.findall(r"\d+\.\d+|\d+", json_data.get("CPUPerc")):
        cpu_limit = int(
            container_cpu_limit(json_data.get("ID")) or psutil.cpu_count(logical=True)
        )
        docker_dump["CPU Usage"] = (
            f"{floater(round((float(cpu_percent[0]) / 100) * cpu_limit, 2))} / {cpu_limit}"
        )
    else:
        docker_dump["CPU Usage"] = "N/A"
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


def containers() -> bool | None:
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
    docker_stats = [
        map_docker_stats(json.loads(line))
        for line in stdout.decode().strip().splitlines()
    ]
    return sorted(docker_stats, key=lambda x: x["Container Name"])


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

    Yields:
        Dict[str, Any]:
        Yields a dictionary of retrieved values.
    """
    from pyudisk import smart_metrics, util

    rendered = {}
    for disk in smart_metrics(smart_lib=models.env.smart_lib):
        if models.OPERATING_SYSTEM == enums.OperatingSystem.linux:
            info = disk.Info
            attributes = disk.Attributes
            if info:
                rendered["model"] = info.Model
            if disk.Partition:
                rendered["mountpoint"] = [
                    partition.MountPoints for partition in disk.Partition
                ]
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
                rendered["updated"] = disk.Attributes.SmartUpdated
        if models.OPERATING_SYSTEM == enums.OperatingSystem.darwin:
            rendered["model"] = disk.model_name or disk.device.name
            rendered["mountpoint"] = disk.mountpoints
            if disk.temperature and disk.temperature.current:
                rendered["temperature"] = (
                    f"{util.celsius_to_fahrenheit(disk.temperature.current)} °F"
                    + " / "
                    + f"{disk.temperature.current} °C"
                )
            if disk.power_on_time and disk.power_on_time.hours:
                rendered["uptime"] = squire.convert_seconds(
                    disk.power_on_time.hours * 3_600
                )
            if disk.smart_status and disk.smart_status.passed:
                rendered["test_status"] = "PASSED"
            rendered["updated"] = disk.local_time.time_t
        # Commonly retrieved for both OS based on the mountpoint location
        if rendered["mountpoint"]:
            rendered["usage"] = squire.total_mountpoints_usage(rendered["mountpoint"])
        else:
            # Usage will be displayed in a table, so this is required
            rendered["usage"] = {
                "Total": "N/A",
                "Used": "N/A",
                "Free": "N/A",
                "Percent": "N/A",
            }
        yield rendered
        # Clear the dict to avoid values being re-used
        rendered.clear()


@cache.timed_cache(60)
def pyudisk_metrics() -> Dict[str, str | List[dict] | int]:
    """Retrieves metrics from PyUdisk library.

    See Also:
        - This is a timed-cache function. Meaning: The output from this function will be cached for 60s.
        - This is to avoid gathering the metrics every 2s, to improve latency and avoid extra overhead.

    Returns:
        List[Dict[str, int | str | float]]:
        List of required metrics as a dictionary of key-value pairs.
    """
    pyudisk_stats = []
    updated = 0
    for metric in get_os_agnostic_metrics():
        updated = metric.get("updated", 60)
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
    return {
        "updated": updated,
        "pyudisk_stats": pyudisk_stats,
    }


async def system_resources() -> Dict[str, dict | List[Dict[str, str | int]]]:
    """Gather system resources including Docker stats asynchronously.

    Returns:
        Dict[str, dict]:
        Returns a nested dictionary.
    """
    # Create tasks for each asynchronous operation
    system_metrics_task = asyncio.create_task(get_system_metrics())
    docker_stats_task = asyncio.create_task(get_docker_stats())
    disk_stats_task = asyncio.create_task(get_disk_info())
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

    # Await all the tasks to complete
    system_metrics = await system_metrics_task
    docker_stats = await docker_stats_task
    disk_stats = await disk_stats_task
    service_stats = await service_stats_task
    process_stats = await process_stats_task
    cpu_usage = await cpu_usage_task

    if models.OPERATING_SYSTEM in (
        enums.OperatingSystem.linux,
        enums.OperatingSystem.darwin,
    ):
        try:
            metrics = pyudisk_metrics()
            updated = round(time.time() - metrics["updated"])
            metrics["pyudisk_updated"] = (
                f"{squire.convert_seconds(updated, 1)} ago"
                if updated >= 100
                else f"{updated} seconds ago"
            )
            system_metrics.update(metrics)
        except ModuleNotFoundError:
            # Expected if module is not installed
            pass
        except Exception as warn:
            LOGGER.warning(warn)

    system_metrics["cpu_usage"] = cpu_usage
    system_metrics["docker_stats"] = docker_stats
    system_metrics["service_stats"] = service_stats
    system_metrics["process_stats"] = process_stats
    system_metrics["disk_info"] = disk_stats
    return system_metrics
