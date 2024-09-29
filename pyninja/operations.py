import asyncio
import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Dict, List, Optional

import psutil

from . import models, squire

LOGGER = logging.getLogger("uvicorn.default")


def default(name: str):
    """Default values for processes and services."""
    return {
        "PID": 0000,
        "Name": name,
        "CPU": "N/A",
        "Memory": "N/A",
        "Uptime": "N/A",
        "Threads": "N/A",
        "Read I/O": "N/A",
        "Write I/O": "N/A",
    }


def get_process_info(
    proc: psutil.Process, process_name: str = None
) -> Dict[str, str | int]:
    """Get process information.

    Args:
        proc: Takes a ``psutil.Process`` object as an argument.
        process_name: Takes a custom process name as an optional argument.

    Returns:
        Dict[str, str | int]:
        Returns a dictionary with process usage statistics.
    """
    # I/O counters don't work on macOS
    try:
        io_counters = proc.io_counters()
        read_io = squire.size_converter(io_counters.read_bytes)
        write_io = squire.size_converter(io_counters.write_bytes)
    except (AttributeError, psutil.AccessDenied) as error:
        LOGGER.debug(error)
        read_io, write_io = "N/A", "N/A"
    try:
        return {
            "PID": proc.pid,
            "Name": process_name or proc.name(),
            "CPU": f"{proc.cpu_percent(models.MINIMUM_CPU_UPDATE_INTERVAL):.2f}%",
            # Resident Set Size
            "Memory": squire.size_converter(proc.memory_info().rss),
            "Uptime": squire.format_timedelta(
                timedelta(seconds=int(time.time() - proc.create_time()))
            ),
            "Threads": proc.num_threads(),
            "Read I/O": read_io,
            "Write I/O": write_io,
        }
    except psutil.Error as error:
        LOGGER.debug(error)
        return default(process_name or proc.name())


async def process_monitor(executor: ThreadPoolExecutor) -> List[Dict[str, str]]:
    """Function to monitor processes and return their usage statistics.

    See Also:
        Process names can be case in-sensitive.

            * macOS/Linux: `top | grep {{ process_name }}`
            * Windows: `Task Manager`

    Returns:
        List[Dict[str, str]]:
        Returns a list of dictionaries with process usage statistics.
    """
    loop = asyncio.get_event_loop()
    tasks = []
    for proc in psutil.process_iter(
        ["pid", "name", "cpu_percent", "memory_info", "create_time"]
    ):
        if any(
            name in proc.name() or name == str(proc.pid)
            for name in models.env.processes
        ):
            tasks.append(loop.run_in_executor(executor, get_process_info, proc))
    return [await task for task in asyncio.as_completed(tasks)]


async def service_monitor(executor: ThreadPoolExecutor) -> List[Dict[str, str]]:
    """Function to monitor services and return their usage statistics.

    See Also:
        Service names are case-sensitive, so use the following command to get the right name.

            * macOS: `launchctl list | grep {{ service_name }}`
            * Linux: `systemctl show {{ service_name }} --property=MainPID`
            * Windows: `sc query {{ service_name }}`

    Returns:
        List[Dict[str, str]]:
        Returns a list of dictionaries with service usage statistics.
    """
    loop = asyncio.get_event_loop()
    tasks = []
    usages = []
    for service_name in models.env.services:
        pid = get_service_pid(service_name)
        if not pid:
            LOGGER.debug(f"Failed to get PID for service: {service_name}")
            usages.append(default(service_name))
            continue
        try:
            proc = psutil.Process(pid)
        except psutil.Error as error:
            LOGGER.debug(error)
            usages.append(default(service_name))
            continue
        tasks.append(
            loop.run_in_executor(executor, get_process_info, proc, service_name)
        )
    for task in asyncio.as_completed(tasks):
        usages.append(await task)
    return usages


def get_service_pid(service_name: str) -> Optional[int]:
    """Retrieve the PID of a service depending on the OS."""
    fn_map = dict(
        linux=get_service_pid_linux,
        darwin=get_service_pid_macos,
        windows=get_service_pid_windows,
    )
    try:
        return fn_map[models.OPERATING_SYSTEM](service_name)
    except (subprocess.SubprocessError, FileNotFoundError) as error:
        LOGGER.debug(error)


def get_service_pid_linux(service_name: str) -> Optional[int]:
    """Get the PID of a service on Linux.

    Args:
        service_name: Name of the service.

    Returns:
        Optional[int]:
        Returns the PID of the service.
    """
    try:
        output = subprocess.check_output(
            ["systemctl", "show", service_name, "--property=MainPID"], text=True
        )
        for line in output.splitlines():
            if line.startswith("MainPID="):
                return int(line.split("=")[1].strip())
    except subprocess.CalledProcessError as error:
        LOGGER.error("{} - {}", error.returncode, error.stderr)


def get_service_pid_macos(service_name: str) -> Optional[int]:
    """Get the PID of a service on macOS.

    Args:
        service_name: Name of the service.

    Returns:
        Optional[int]:
        Returns the PID of the service.
    """
    try:
        output = subprocess.check_output(["launchctl", "list"], text=True)
        for line in output.splitlines():
            if service_name in line:
                return int(line.split()[0])  # Assuming PID is the first column
    except subprocess.CalledProcessError as error:
        LOGGER.error("{} - {}", error.returncode, error.stderr)


def get_service_pid_windows(service_name: str) -> Optional[int]:
    """Get the PID of a service on Windows.

    Args:
        service_name: Name of the service.

    Returns:
        Optional[int]:
        Returns the PID of the service.
    """
    try:
        output = subprocess.check_output(["sc", "query", service_name], text=True)
        for line in output.splitlines():
            if "PID" in line:
                return int(line.split(":")[1].strip())
    except subprocess.CalledProcessError as error:
        LOGGER.error("{} - {}", error.returncode, error.stderr)
