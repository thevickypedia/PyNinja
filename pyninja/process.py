import logging
from collections.abc import Generator
from typing import Dict

import psutil

LOGGER = logging.getLogger("uvicorn.error")


def get_process_status(process_name: str) -> Generator[Dict[str, int]]:
    """Get process information by name.

    Args:
        process_name: Name of the process.

    Yields:
        Generator[Dict[str, int]]:
        Yields the process metrics as a dictionary of key-value pairs.
    """
    # todo: implement concurrency
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.name().lower() == process_name.lower():
            process = psutil.Process(proc.pid)
            process._name = process_name
            try:
                perf_report = get_performance(process)
                LOGGER.info({f"{process_name} [{process.pid}]": perf_report})
                perf_report["pname"] = process_name
                perf_report["zombie"] = False
                yield perf_report
            except psutil.ZombieProcess as warn:
                LOGGER.warning(warn)
                yield {"zombie": True, "process_name": process_name}


def get_performance(process: psutil.Process) -> Dict[str, int | float]:
    """Checks performance by monitoring CPU utilization, number of threads and open files.

    Args:
        process: Process object.

    Returns:
        Dict[str, int]:
        Returns the process metrics as key-value pairs.
    """
    cpu = process.cpu_percent(interval=0.5)
    threads = process.num_threads()
    open_files = len(process.open_files())
    return {
        "cpu": cpu,
        "threads": threads,
        "open_files": open_files,
        "pid": process.pid.real,
    }
