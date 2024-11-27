import asyncio
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import time
from datetime import timedelta
from typing import Any, Dict, List

import psutil

from pyninja.executors import squire
from pyninja.features import cpu, disks, gpu, operations
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
    if gpu_names := gpu.get_names():
        LOGGER.info(gpu_names)
        sys_info_basic["GPU"] = ", ".join(
            [gpu_info.get("model") for gpu_info in gpu_names]
        )
    if processor_name := cpu.get_name():
        LOGGER.info("Processor: %s", processor_name)
        sys_info_basic["CPU"] = processor_name
    sys_info_mem_storage = {
        "Memory": squire.size_converter(psutil.virtual_memory().total),
        "Disk": squire.size_converter(shutil.disk_usage("/").total),
    }
    if swap := psutil.swap_memory().total:
        sys_info_mem_storage["Swap"] = squire.size_converter(swap)
    sys_info_network = {
        "Private IP address": squire.private_ip_address(),
        "Public IP address": squire.public_ip_address(),
    }
    return dict(
        logout="/logout",
        sys_info_basic=dict(sorted(sys_info_basic.items())),
        sys_info_mem_storage=dict(sorted(sys_info_mem_storage.items())),
        sys_info_network=sys_info_network,
        sys_info_disks=disks.get_all_disks(),
    )


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
    m1, m5, m15 = os.getloadavg() or (None, None, None)
    return dict(
        memory_info=psutil.virtual_memory()._asdict(),
        swap_info=psutil.swap_memory()._asdict(),
        load_averages=dict(m1=m1, m5=m5, m15=m15),
    )


@cache.timed_cache(60)
def pyudisk_metrics() -> List[Dict[str, int | str | float]]:
    """Retrieves metrics from PyUdisk library.

    See Also:
        - This is a timed-cache function. Meaning: The output from this function will be cached for 60s.
        - This is avoid gathering the metrics every 2s, to improve latency and avoid extra overhead.

    Returns:
        List[Dict[str, int | str | float]]:
        List of required metrics as a dictionary of key-value pairs.
    """
    from pyudisk import EnvConfig, smart_metrics, util

    pyudisk_stats = []
    disk = None
    for disk in smart_metrics(EnvConfig(udisk_lib=models.env.udisk_lib)):
        pyudisk_stats.append(
            {
                **{
                    "Model": disk.Info.Model,
                    "Mountpoint": str(disk.Partition.MountPoints),
                    "Temperature": (
                        f"{util.kelvin_to_fahrenheit(disk.Attributes.SmartTemperature)} °F"
                        + " / "
                        + f"{util.kelvin_to_celsius(disk.Attributes.SmartTemperature)} °C"
                    ),
                    "Bad Sectors": disk.Attributes.SmartNumBadSectors,
                    "Test Status": disk.Attributes.SmartSelftestStatus,
                    "Uptime": squire.convert_seconds(
                        disk.Attributes.SmartPowerOnSeconds
                    ),
                },
                **disk.Usage.model_dump(),
            }
        )
    # Smart metrics are gathered at certain system intervals - so no need to get this attr from all the drives
    updated = round(time.time() - disk.Attributes.SmartUpdated)
    return {
        "pyudisk_updated": (
            f"{squire.convert_seconds(updated, 1)} ago"
            if updated >= 100
            else f"{updated} seconds ago"
        ),
        "pyudisk_stats": pyudisk_stats,
    }


async def system_resources() -> Dict[str, dict]:
    """Gather system resources including Docker stats asynchronously.

    Returns:
        Dict[str, dict]:
        Returns a nested dictionary.
    """
    # todo: Redo disk charts entirely
    #   1. Change "Disk Information" collapsible section similar to docker/service/process stats table
    #   2. Remove "Disk" from "Memory and Storage" and move the remaining under "System Information"
    #   3. Create a 4th section for disk usage - that includes PIE charts for all the attached disks
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
    if models.OPERATING_SYSTEM == enums.OperatingSystem.linux:
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
