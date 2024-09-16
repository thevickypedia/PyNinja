import logging
import shutil
import subprocess
from http import HTTPStatus
from typing import List, Optional

import psutil
from fastapi import Depends, Header, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBearer
from pydantic import PositiveFloat, PositiveInt

from . import (
    auth,
    disks,
    dockerized,
    exceptions,
    models,
    process,
    processor,
    service,
    squire,
)

LOGGER = logging.getLogger("uvicorn.default")
BASIC_AUTH = HTTPBasic()
BEARER_AUTH = HTTPBearer()


async def get_ip_address(
    request: Request,
    public: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get local and public IP address of the device.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - public: Boolean flag to get the public IP address.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and the public/private IP as response.
    """
    await auth.level_1(request, apikey)
    if public:
        return squire.public_ip_address()
    else:
        return squire.private_ip_address()


async def get_cpu_utilization(
    request: Request,
    interval: int | float = 2,
    per_cpu: bool = True,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get the CPU utilization.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - interval: Interval to get the CPU utilization.
        - per_cpu: If True, returns the CPU utilization for each CPU.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and CPU usage as response.
    """
    await auth.level_1(request, apikey)
    if per_cpu:
        cpu_percentages = psutil.cpu_percent(interval=interval, percpu=True)
        usage = {f"cpu{i + 1}": percent for i, percent in enumerate(cpu_percentages)}
    else:
        usage = {"cpu": psutil.cpu_percent(interval=interval, percpu=False)}
    raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=usage)


async def get_memory_utilization(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get memory utilization.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and CPU usage as response.
    """
    await auth.level_1(request, apikey)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.OK.real,
        detail={
            "ram_total": squire.size_converter(psutil.virtual_memory().total),
            "ram_used": squire.size_converter(psutil.virtual_memory().used),
            "ram_usage": psutil.virtual_memory().percent,
            "swap_total": squire.size_converter(psutil.swap_memory().total),
            "swap_used": squire.size_converter(psutil.swap_memory().used),
            "swap_usage": psutil.swap_memory().percent,
        },
    )


async def get_cpu_load_avg(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get the number of processes in the system run queue averaged over the last 1, 5, and 15 minutes respectively.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and CPU usage as response.
    """
    await auth.level_1(request, apikey)
    m1, m5, m15 = psutil.getloadavg() or (None, None, None)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.OK.real,
        detail=dict(m1=m1, m5=m5, m15=m15),
    )


async def get_disk_utilization(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get disk utilization.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and CPU usage as response.
    """
    await auth.level_1(request, apikey)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.OK.real,
        detail={
            k: squire.size_converter(v)
            for k, v in shutil.disk_usage("/")._asdict().items()
        },
    )


async def get_all_disks(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get all disks attached to the host device.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and attached disks as response.
    """
    await auth.level_1(request, apikey)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.OK.real,
        detail=disks.get_all_disks(),
    )


async def run_command(
    request: Request,
    payload: models.Payload,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """**API function to run a command on host machine.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - payload: Payload received as request body.
        - apikey: API Key to authenticate the request.
        - token: API secret to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_2(request, apikey, token)
    LOGGER.info(
        "Requested command: '%s' with timeout: %ds", payload.command, payload.timeout
    )
    try:
        response = squire.process_command(payload.command, payload.timeout)
    except subprocess.TimeoutExpired as warn:
        LOGGER.warning(warn)
        raise exceptions.APIResponse(
            status_code=HTTPStatus.REQUEST_TIMEOUT, detail=warn.__str__()
        )
    raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=response)


async def get_process_status(
    request: Request,
    process_name: str,
    cpu_interval: PositiveInt | PositiveFloat = 1,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to monitor a process.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - process_name: Name of the process to check status.
        - cpu_interval: Interval in seconds to get the CPU usage.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if response := process.get_process_status(process_name, cpu_interval):
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=response)
    LOGGER.error("%s: 404 - No such process", process_name)
    raise exceptions.APIResponse(
        status_code=404, detail=f"Process {process_name} not found."
    )


async def get_service_status(
    request: Request,
    service_name: str,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to monitor a service.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - service_name: Name of the service to check status.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    response = service.get_service_status(service_name)
    LOGGER.info(
        "%s: %d - %s",
        service_name,
        response.status_code,
        response.description,
    )
    raise exceptions.APIResponse(
        status_code=response.status_code, detail=response.description
    )


async def get_docker_containers(
    request: Request,
    container_name: str = None,
    get_all: bool = False,
    get_running: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get docker containers' information.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - container_name: Name of the container to check status.
        - get_all: Get all the containers' information.
        - get_running: Get running containers' information.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if get_all:
        if all_containers := dockerized.get_all_containers():
            raise exceptions.APIResponse(
                status_code=HTTPStatus.OK.real, detail=all_containers
            )
        raise exceptions.APIResponse(
            status_code=HTTPStatus.NOT_FOUND.real, detail="No containers found!"
        )
    if get_running:
        if running_containers := list(dockerized.get_running_containers()):
            raise exceptions.APIResponse(
                status_code=HTTPStatus.OK.real, detail=running_containers
            )
        raise exceptions.APIResponse(
            status_code=HTTPStatus.NOT_FOUND.real, detail="No running containers found!"
        )
    if container_name:
        if container_status := dockerized.get_container_status(container_name):
            raise exceptions.APIResponse(
                status_code=HTTPStatus.OK.real, detail=container_status
            )
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
            detail="Unable to get container status!",
        )
    raise exceptions.APIResponse(
        status_code=HTTPStatus.BAD_REQUEST.real,
        detail="Either 'container_name' or 'get_all' or 'get_running' should be set",
    )


async def get_docker_images(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get docker images' information.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if images := dockerized.get_all_images():
        LOGGER.info(images)
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=images)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
        detail="Unable to get docker images!",
    )


async def get_docker_volumes(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get docker volumes' information.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if volumes := dockerized.get_all_volumes():
        LOGGER.info(volumes)
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=volumes)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
        detail="Unable to get docker volumes!",
    )


async def get_docker_stats(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get docker-stats for all running containers.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and attached disks as response.
    """
    await auth.level_1(request, apikey)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.OK.real,
        detail=list(squire.get_docker_stats()),
    )


async def get_processor_name(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get process information.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - process_name: Name of the process to get information.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if processor_info := processor.get_name():
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real, detail=processor_info
        )
    raise exceptions.APIResponse(
        status_code=HTTPStatus.NOT_FOUND.real,
        detail="Unable to retrieve processor information!",
    )


async def docs() -> RedirectResponse:
    """Redirect to docs page.

    Returns:
        RedirectResponse:
        Redirects the user to ``/docs`` page.
    """
    return RedirectResponse("/docs")


async def health():
    """Health check for PyNinja.

    Returns:
        APIResponse:
        Returns a health check response with status code 200.
    """
    raise exceptions.APIResponse(status_code=HTTPStatus.OK, detail=HTTPStatus.OK.phrase)


def get_all_routes(dependencies: List[Depends]) -> List[APIRoute]:
    """Get all the routes to be added for the API server.

    Args:
        dependencies: List of dependencies to be added to the routes

    Returns:
        List[APIRoute]:
        Returns the routes as a list of APIRoute objects.
    """
    routes = [
        APIRoute(path="/", endpoint=docs, methods=["GET"], include_in_schema=False),
        APIRoute(
            path="/health", endpoint=health, methods=["GET"], include_in_schema=False
        ),
        APIRoute(
            path="/get-ip",
            endpoint=get_ip_address,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-cpu",
            endpoint=get_cpu_utilization,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-cpu-load",
            endpoint=get_cpu_load_avg,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-processor",
            endpoint=get_processor_name,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-memory",
            endpoint=get_memory_utilization,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-disk",
            endpoint=get_disk_utilization,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-all-disks",
            endpoint=get_all_disks,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/service-status",
            endpoint=get_service_status,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/process-status",
            endpoint=get_process_status,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-container",
            endpoint=get_docker_containers,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-image",
            endpoint=get_docker_images,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-volume",
            endpoint=get_docker_volumes,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-stats",
            endpoint=get_docker_stats,
            methods=["GET"],
            dependencies=dependencies,
        ),
    ]
    return routes
