import json
import logging
import shutil
import subprocess
from collections.abc import Generator
from http import HTTPStatus
from typing import Dict

from pyninja.modules import enums, models

LOGGER = logging.getLogger("uvicorn.default")


def running(service_name: str) -> models.ServiceStatus:
    """Constructs an ServiceStatus object with a status code.

    Args:
        service_name: Name of the service.

    Returns:
        ServiceStatus:
        Returns a reference to the ServiceStatus object.
    """
    return models.ServiceStatus(
        status_code=HTTPStatus.OK.real,
        description=f"{service_name} is running",
        service_name=service_name,
    )


def stopped(service_name: str) -> models.ServiceStatus:
    """Constructs an ServiceStatus object with a status code 501.

    Args:
        service_name: Name of the service.

    Returns:
        ServiceStatus:
        Returns a reference to the ServiceStatus object.
    """
    return models.ServiceStatus(
        status_code=HTTPStatus.NOT_IMPLEMENTED.real,
        description=f"{service_name} has been stopped",
        service_name=service_name,
    )


def unknown(service_name) -> models.ServiceStatus:
    """Constructs an ServiceStatus object with a status code 503.

    Args:
        service_name: Name of the service.

    Returns:
        ServiceStatus:
        Returns a reference to the ServiceStatus object.
    """
    return models.ServiceStatus(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
        description=f"{service_name} - status unknown",
        service_name=service_name,
    )


def unavailable(service_name: str) -> models.ServiceStatus:
    """Constructs an ServiceStatus object with a status code 404.

    Args:
        service_name: Name of the service.

    Returns:
        ServiceStatus:
        Returns a reference to the ServiceStatus object.
    """
    return models.ServiceStatus(
        status_code=HTTPStatus.NOT_FOUND.real,
        description=f"{service_name} - not found",
        service_name=service_name,
    )


def get_all_services() -> Generator[Dict[str, str]]:
    """OS-agnostic function to list all the services available and their status.

    Yields:
        Dict[str, str]:
        Yields all the services as key-value pairs.
    """
    if models.OPERATING_SYSTEM == enums.OperatingSystem.linux:
        try:
            output = subprocess.check_output(
                [models.env.service_lib, "list-units", "--output=json"],
                text=True,
            ).strip()
            service_list = json.loads(output)
            for service in service_list:
                if service["unit"].endswith(".service"):
                    yield service
            return
        except subprocess.CalledProcessError as error:
            LOGGER.error("%s", error)
            return

    if models.OPERATING_SYSTEM == enums.OperatingSystem.darwin:
        try:
            output = subprocess.check_output(
                [models.env.service_lib, "list"], text=True
            )
            for line in output.splitlines()[1:]:
                pid, status, label = line.split("\t", 2)
                if status == "0":
                    state = "running"
                elif status == "-9":
                    state = "killed"
                else:
                    LOGGER.debug("Unknown service state: %s", line)
                    state = "unknown"
                if label.startswith("application."):
                    yield {"PID": pid, "status": state, "label": label}
            return
        except subprocess.CalledProcessError as error:
            LOGGER.error("%s", error)
            return

    if models.OPERATING_SYSTEM == enums.OperatingSystem.windows:
        try:
            powershell = shutil.which("pwsh") or shutil.which("powershell")
            # command = f"{models.env.service_lib} query type=service state=all | ConvertTo-Json -Depth 3"
            result = subprocess.run(
                [powershell, '-Command', '$WarningPreference = "SilentlyContinue"; Get-Service | ConvertTo-Json -Depth 3'],
                capture_output=True, text=True, check=False
            )
            # output = "\n".join(result.stdout.splitlines()[1:]).strip()
            keys_required = [
                'CanPauseAndContinue',
                'CanShutdown',
                'CanStop',
                'DisplayName',
                # 'DependentServices',
                'MachineName',
                'ServiceName',
                # 'ServicesDependedOn',
                'StartType',
                'ServiceHandle',
                'Status',
                'ServiceType',
                'Site',
                'Container',
                'UserName',
                'Description',
                'DelayedAutoStart',
                'BinaryPathName',
                'StartupType',
                'Name',
                # 'RequiredServices'
            ]
            output = json.loads(result.stdout)
            for service in output:
                service_info = {}
                for key, value in service.items():
                    if key in keys_required:
                        service_info[key] = value
                yield service_info
        except subprocess.CalledProcessError as error:
            LOGGER.error("%s", error)
            return


def get_service_status(service_name: str) -> models.ServiceStatus:
    """Get service status by name.

    Args:
        service_name: Name of the service.

    Returns:
        ServiceStatus:
        Returns an instance of the ServiceStatus object.
    """
    if models.OPERATING_SYSTEM == enums.OperatingSystem.linux:
        try:
            output = subprocess.check_output(
                [models.env.service_lib, "is-active", service_name],
                text=True,
            ).strip()
            if output == "active":
                return running(service_name)
            elif output == "inactive":
                return stopped(service_name)
            else:
                return models.ServiceStatus(
                    status_code=HTTPStatus.NOT_IMPLEMENTED.real,
                    description=f"{service_name} - {output}",
                    service_name=service_name,
                )
        except subprocess.CalledProcessError as error:
            if error.returncode == 3:
                return stopped(service_name)
            LOGGER.error("%d - %s", 404, error)
            return unavailable(service_name)

    if models.OPERATING_SYSTEM == enums.OperatingSystem.darwin:
        try:
            output = subprocess.check_output(
                [models.env.service_lib, "list"], text=True
            )
            for line in output.splitlines():
                if service_name in line:
                    return running(line.split()[-1])
            else:
                return stopped(service_name)
        except subprocess.CalledProcessError as error:
            LOGGER.error("%d - %s", 404, error)
            return unavailable(service_name)

    if models.OPERATING_SYSTEM == enums.OperatingSystem.windows:
        try:
            output = subprocess.check_output(
                [models.env.service_lib, "query", service_name],
                text=True,
            )
            if "RUNNING" in output:
                return running(service_name)
            elif "STOPPED" in output:
                return stopped(service_name)
            else:
                return unknown(service_name)
        except subprocess.CalledProcessError as error:
            LOGGER.error("%d - %s", 404, error)
            return unavailable(service_name)


def stop_service(service_name: str):
    """Stop a service by name.

    Args:
        service_name: Name of the service.

    Returns:
        ServiceStatus:
        Returns an instance of the ServiceStatus object.
    """
    service_status = get_service_status(service_name)
    if service_status.status_code != HTTPStatus.OK.real:
        return service_status
    # Update service_name to the one fetched from launchctl (for macOS)
    service_name = service_status.service_name
    try:
        subprocess.check_output(
            [models.env.service_lib, "stop", service_name],
            text=True,
        )
        return stopped(service_name)
    except subprocess.CalledProcessError as error:
        LOGGER.error("%d - %s", 404, error)
        return unavailable(service_name)


def start_service(service_name: str):
    """Start a service by name.

    Args:
        service_name: Name of the service.

    Returns:
        ServiceStatus:
        Returns an instance of the ServiceStatus object.
    """
    service_status = get_service_status(service_name)
    if service_status.status_code == HTTPStatus.OK.real:
        return service_status
    # Update service_name to the one fetched from launchctl (for macOS)
    service_name = service_status.service_name
    try:
        subprocess.check_output(
            [models.env.service_lib, "start", service_name],
            text=True,
        )
        return stopped(service_name)
    except subprocess.CalledProcessError as error:
        LOGGER.error("%d - %s", 404, error)
        return unavailable(service_name)
