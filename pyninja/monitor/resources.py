import asyncio
import json
import logging
import os
import platform
import shutil
import subprocess
import time
from datetime import timedelta
from typing import Any, Dict, List

import psutil

from pyninja.executors import squire
from pyninja.features import cpu, disks, gpu, operations
from pyninja.modules import models

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


def map_docker_stats(json_data: Dict[str, str]) -> Dict[str, str]:
    """Map the JSON data to a dictionary.

    Args:
        json_data: JSON data from the docker stats command.

    Returns:
        Dict[str, str]:
        Returns a dictionary with container stats.
    """
    return {
        "Container ID": json_data.get("ID"),
        "Container Name": json_data.get("Name"),
        "CPU": json_data.get("CPUPerc"),
        "Memory": json_data.get("MemPerc"),
        "Memory Usage": json_data.get("MemUsage"),
        "Block I/O": json_data.get("BlockIO"),
        "Network I/O": json_data.get("NetIO"),
    }


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


async def system_resources() -> Dict[str, dict]:
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

    system_metrics["cpu_usage"] = cpu_usage
    system_metrics["docker_stats"] = docker_stats
    system_metrics["service_stats"] = service_stats
    system_metrics["process_stats"] = process_stats
    return system_metrics
