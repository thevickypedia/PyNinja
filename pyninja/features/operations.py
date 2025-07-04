import asyncio
import logging
import subprocess
import time
from datetime import timedelta
from typing import Dict, List, Optional

import psutil

from pyninja.executors import squire
from pyninja.modules import models

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
        "Open Files": "N/A",
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
            "Open Files": len(proc.open_files()),
            "Read I/O": read_io,
            "Write I/O": write_io,
        }
    except psutil.Error as error:
        LOGGER.debug(error)
        return default(process_name)


async def process_monitor(processes: List[str]) -> List[Dict[str, str]]:
    """Function to monitor processes and return their usage statistics.

    Args:
        processes: List of process names to monitor.

    See Also:
        Process names can be case in-sensitive as they are not strictly matched.

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
            name.lower() == proc.name().lower() or name == str(proc.pid)
            for name in processes
        ):
            tasks.append(
                loop.run_in_executor(
                    models.EXECUTOR, get_process_info, proc, proc.name()
                )
            )
    completed_tasks = []
    for task in asyncio.as_completed(tasks):
        try:
            completed_tasks.append(await task)
        except psutil.Error as error:
            LOGGER.debug(error)
    return completed_tasks


async def service_monitor(services: List[str]) -> List[Dict[str, str]]:
    """Function to monitor services and return their usage statistics.

    Args:
        services: List of service names to monitor.

    See Also:
        Service names are case-sensitive as they are strictly matched. Use the following command to get the right name.

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
    for service_name in services:
        pid = get_service_pid(service_name)
        if not pid:
            LOGGER.debug(f"Failed to get PID for service: {service_name}")
            # This is to give visibility on a service that was meant to be monitored
            usages.append(default(service_name))
            continue
        try:
            proc = psutil.Process(pid)
        except psutil.Error as error:
            LOGGER.debug(error)
            usages.append(default(service_name))
            continue
        tasks.append(
            loop.run_in_executor(models.EXECUTOR, get_process_info, proc, service_name)
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
            [models.env.service_lib, "show", service_name, "--property=MainPID"],
            text=True,
        )
        for line in output.splitlines():
            if line.startswith("MainPID="):
                return int(line.split("=")[1].strip())
    except subprocess.CalledProcessError as error:
        LOGGER.debug("%s - %s", error.returncode, error.stderr)


def get_service_pid_macos(service_name: str) -> Optional[int]:
    """Get the PID of a service on macOS.

    Args:
        service_name: Name of the service.

    Returns:
        Optional[int]:
        Returns the PID of the service.
    """
    service_name = service_name.lower()
    try:
        output = subprocess.check_output([models.env.service_lib, "list"], text=True)
        for line in output.splitlines()[1:]:  # Skip the header
            if service_name in line.lower():
                try:
                    return int(line.split()[0])
                except ValueError:
                    return 0
    except subprocess.CalledProcessError as error:
        LOGGER.debug("%s - %s", error.returncode, error.stderr)


def get_service_pid_windows(service_name: str) -> Optional[int]:
    """Get the PID of a service on Windows.

    Args:
        service_name: Name of the service.

    Returns:
        Optional[int]:
        Returns the PID of the service.
    """
    try:
        output = subprocess.check_output(
            [models.env.service_lib, "query", service_name], text=True
        )
        for line in output.splitlines():
            if "PID" in line:
                return int(line.split(":")[1].strip())
    except subprocess.CalledProcessError as error:
        LOGGER.debug("%s - %s", error.returncode, error.stderr)
