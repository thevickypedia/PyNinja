import logging
from concurrent.futures import as_completed
from typing import Dict, List

import psutil
from pydantic import PositiveInt

from pyninja.modules import models

LOGGER = logging.getLogger("uvicorn.default")


def get_process_status(
    process_name: str, cpu_interval: PositiveInt
) -> List[Dict[str, int | float | str | bool]]:
    """Get process information by name.

    Args:
        process_name: Name of the process.
        cpu_interval: CPU interval to get the CPU performance.

    Returns:
        List[Dict[str, int | float | str | bool]]:
        Returns a list of performance report for each process hosting the given process name.
    """
    result = []
    futures = {}
    with models.EXECUTOR:
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.name().lower() == process_name.lower():
                future = models.EXECUTOR.submit(
                    get_performance, process=proc, cpu_interval=cpu_interval
                )
                futures[future] = proc.name()
    for future in as_completed(futures):
        if future.exception():
            LOGGER.error(
                "Thread processing for '%s' received an exception: %s",
                futures[future],
                future.exception(),
            )
        else:
            result.append(future.result())
    return result


def get_performance(
    process: psutil.Process, cpu_interval: PositiveInt
) -> Dict[str, int | float | str | bool]:
    """Checks process performance by monitoring CPU utilization, number of threads and open files.

    Args:
        process: Process object.
        cpu_interval: CPU interval to get the CPU performance.

    Returns:
        Dict[str, int | float | str | bool]:
        Returns the process metrics as key-value pairs.
    """
    try:
        cpu = process.cpu_percent(interval=cpu_interval)
        threads = process.num_threads()
        open_files = len(process.open_files())
        perf_report = {
            "pid": process.pid.real,
            "pname": process.name(),
            "cpu": cpu,
            "threads": threads,
            "open_files": open_files,
            "zombie": False,
        }
        LOGGER.info({f"{process.name()} [{process.pid}]": perf_report})
    except psutil.ZombieProcess as warn:
        LOGGER.warning(warn)
        perf_report = {"zombie": True, "process_name": process.name()}
    return perf_report
