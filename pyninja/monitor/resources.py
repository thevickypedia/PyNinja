import asyncio
import json
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict

import psutil

from .. import operations

# Use a ThreadPoolExecutor to run blocking functions in separate threads
EXECUTOR = ThreadPoolExecutor(max_workers=os.cpu_count())
LOGGER = logging.getLogger("uvicorn.default")


def get_cpu_percent() -> List[float]:
    """Get CPU usage percentage.

    Returns:
        List[float]:
        Returns a list of CPU percentages.
    """
    return psutil.cpu_percent(interval=1, percpu=True)


async def get_docker_stats() -> List[Dict[str, str]]:
    """Run the docker stats command asynchronously and parse the output.

    Returns:
        List[Dict[str, str]]:
        Returns a list of key-value pairs with the container stat and value.
    """
    process = await asyncio.create_subprocess_shell(
        'docker stats --no-stream --format "{{json .}}"',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if stderr:
        LOGGER.error(stderr.decode())
        return []
    return [json.loads(line) for line in stdout.decode().strip().splitlines()]


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
        disk_info=shutil.disk_usage("/")._asdict(),
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
    service_stats_task = asyncio.create_task(operations.service_monitor())
    process_stats_task = asyncio.create_task(operations.process_monitor())

    # CPU percent check is a blocking call and cannot be awaited, so run it in a separate thread
    loop = asyncio.get_event_loop()
    cpu_usage_task = loop.run_in_executor(EXECUTOR, get_cpu_percent)

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