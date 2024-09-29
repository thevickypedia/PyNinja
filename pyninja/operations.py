import logging
import subprocess
import time
from datetime import timedelta
from typing import List, Optional, Dict

import psutil

from . import squire, models

LOGGER = logging.getLogger("uvicorn.default")


def default(name: str):
    return dict(
        name=name,
        pid=0,
        memory="N/A",
        cpu="N/A",
        uptime="N/A",
        read_io="N/A",
        write_io="N/A",
    )


def get_process_info(proc: psutil.Process):
    cpu_usage = proc.cpu_percent()
    memory_usage = proc.memory_info().rss  # Resident Set Size
    cpu = f"{cpu_usage:.2f}%"
    memory = squire.size_converter(memory_usage)
    pid = proc.pid
    threads = proc.num_threads()
    uptime = squire.format_timedelta(
        timedelta(seconds=int(time.time() - proc.create_time()))
    )

    # I/O counters don't work on macOS
    try:
        io_counters = proc.io_counters()
        read_io = squire.size_converter(io_counters.read_bytes)
        write_io = squire.size_converter(io_counters.write_bytes)
    except AttributeError:
        read_io, write_io = "N/A", "N/A"

    return dict(
        name=proc.name(),
        pid=pid,
        cpu=cpu,
        memory=memory,
        uptime=uptime,
        threads=threads,
        read_io=read_io,
        write_io=write_io,
    )


async def process_monitor() -> List[Dict[str, str]]:
    usages = []
    for proc in psutil.process_iter(
        ["pid", "name", "cpu_percent", "memory_info", "create_time"]
    ):
        try:
            if any(name in proc.name() for name in models.env.processes):
                usages.append(get_process_info(proc))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            usages.append(default(proc.name()))
            continue
    return usages


async def service_monitor() -> List[Dict[str, str]]:
    """

    See Also:
        Service names are case-sensitive, so use the following command to get the right name.

            * macOS: `launchctl list | grep {{ service_name }}`
            * Linux: `systemctl show {{ service_name }} --property=MainPID`
            * Windows: `sc query {{ service_name }}`
    """
    usages = []
    for service_name in models.env.services:
        pid = get_service_pid(service_name)
        if not pid:
            LOGGER.debug(f"Failed to get PID for service: {service_name}")
            usages.append(default(service_name))
            continue
        try:
            proc = psutil.Process(pid)
        except psutil.NoSuchProcess:
            LOGGER.debug(f"Process with PID {pid} not found")
            usages.append(default(service_name))
            continue
        usage = get_process_info(proc)
        usages.append(usage)
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
    try:
        output = subprocess.check_output(["launchctl", "list"], text=True)
        for line in output.splitlines():
            if service_name in line:
                return int(line.split()[0])  # Assuming PID is the first column
    except subprocess.CalledProcessError as error:
        LOGGER.error("{} - {}", error.returncode, error.stderr)


def get_service_pid_windows(service_name: str) -> Optional[int]:
    try:
        output = subprocess.check_output(["sc", "query", service_name], text=True)
        for line in output.splitlines():
            if "PID" in line:
                return int(line.split(":")[1].strip())
    except subprocess.CalledProcessError as error:
        LOGGER.error("{} - {}", error.returncode, error.stderr)
