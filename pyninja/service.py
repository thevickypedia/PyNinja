import platform
import subprocess
from http import HTTPStatus

from pyninja import exceptions, models

current_os = platform.system()

if current_os not in ("Darwin", "Linux", "Windows"):
    raise exceptions.UnSupportedOS(
        f"{current_os} is unsupported.\n\t"
        "Host machine should either be macOS, Windows or any of Linux distros"
    )


def get_service_status(service_name: str) -> models.ServiceStatus:
    """Get service status by name.

    Args:
        service_name: Name of the service.

    Returns:
        ServiceStatus:
        Returns an instance of the ServiceStatus object.
    """
    running = models.ServiceStatus(
        status_code=HTTPStatus.OK.real,
        description=f"{service_name} is running",
    )

    stopped = models.ServiceStatus(
        status_code=HTTPStatus.NOT_IMPLEMENTED.real,
        description=f"{service_name} has been stopped",
    )

    unknown = models.ServiceStatus(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
        description=f"{service_name} - status unknwon",
    )

    unavailable = models.ServiceStatus(
        status_code=HTTPStatus.NOT_FOUND.real,
        description=f"{service_name} - not found",
    )

    if current_os == "Windows":
        # Windows: Use sc command
        cmd = f"sc query {service_name}"
        try:
            output = subprocess.check_output(cmd, shell=True, text=True)
            if "RUNNING" in output:
                return running
            elif "STOPPED" in output:
                return stopped
            else:
                return unknown
        except subprocess.CalledProcessError:
            return unavailable

    if current_os == "Linux":
        # Linux: Use systemctl
        cmd = f"systemctl is-active {service_name}"
        try:
            output = subprocess.check_output(cmd, shell=True, text=True).strip()
            if output == "active":
                return running
            elif output == "inactive":
                return stopped
            else:
                return models.ServiceStatus(
                    status_code=HTTPStatus.NOT_IMPLEMENTED.real,
                    description=f"{service_name} - {output}",
                )
        except subprocess.CalledProcessError:
            return unavailable

    if current_os == "Darwin":
        # macOS: Use launchctl
        cmd = f"launchctl list | grep {service_name}"
        try:
            output = subprocess.check_output(cmd, shell=True, text=True)
            if service_name in output:
                return running
            else:
                return stopped
        except subprocess.CalledProcessError:
            return unavailable