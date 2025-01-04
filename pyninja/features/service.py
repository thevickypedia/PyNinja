import logging
import subprocess
from http import HTTPStatus

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
