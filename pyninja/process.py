import logging
from collections.abc import Generator
from typing import Dict

import psutil

LOGGER = logging.getLogger("uvicorn.error")


def get_process_status(process_name: str) -> Generator[Dict[str, int]]:
    """Get process ID for a particular service.

    Args:
        service_name (str): Name of the service.

    Yields:
        Generator[Dict[str, int]]:
        Yields the process metrics as a dictionary of key-value pairs.
    """
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.info["name"].lower() == process_name.lower():
            process = psutil.Process(proc.info["pid"])
            yield get_performance(process_name, process)


def get_performance(process_name: str, process: psutil.Process) -> Dict[str, int]:
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
    info_dict = {"cpu": cpu, "threads": threads, "open_files": open_files}
    LOGGER.info({f"{process_name} [{process.pid}]": info_dict})
    info_dict["pid"] = process.pid.real
    info_dict["pname"] = process_name
    return info_dict
