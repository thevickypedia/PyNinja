import asyncio
import logging
import subprocess
import time
from http import HTTPStatus
from typing import List, Optional

import psutil
from fastapi import Depends, Header, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.websockets import WebSocket, WebSocketDisconnect, WebSocketState
from pydantic import PositiveFloat, PositiveInt

from pyninja import (
    auth,
    dockerized,
    exceptions,
    models,
    process,
    rate_limit,
    service,
    squire,
)

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def get_ip(
    request: Request,
    public: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """Get local and public IP address of the device.

    Args:
        request: Reference to the FastAPI request object.
        public: Boolean flag to get the public IP address.
        apikey: API Key to authenticate the request.
        token: API secret to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and the public/private IP as response.
    """
    await auth.level_1(request, apikey)
    if public:
        return squire.public_ip_address()
    else:
        return squire.private_ip_address()


async def get_cpu(
    request: Request,
    interval: int | float = 2,
    per_cpu: bool = True,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """Get the CPU utilization.

    **Args:**

        request: Reference to the FastAPI request object.
        interval: Interval to get the CPU utilization.
        per_cpu: If True, returns the CPU utilization for each CPU.
        apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and CPU usage as response.
    """
    await auth.level_1(request, apikey)
    if per_cpu:
        cpu_percentages = psutil.cpu_percent(interval=interval, percpu=True)
        usage = {f"cpu{i+1}": percent for i, percent in enumerate(cpu_percentages)}
    else:
        usage = {"cpu": psutil.cpu_percent(interval=interval, percpu=False)}
    raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=usage)


async def get_memory(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """Get memory utilization.

    **Args:**

        request: Reference to the FastAPI request object.
        apikey: API Key to authenticate the request.

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


async def run_command(
    request: Request,
    payload: models.Payload,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """**API function to run a command on host machine.**

    **Args:**

        request: Reference to the FastAPI request object.
        payload: Payload received as request body.
        apikey: API Key to authenticate the request.
        token: API secret to authenticate the request.

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


async def process_status(
    request: Request,
    process_name: str,
    cpu_interval: PositiveInt | PositiveFloat = 1,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to monitor a process.**

    **Args:**

        request: Reference to the FastAPI request object.
        process_name: Name of the process to check status.
        cpu_interval: Interval in seconds to get the CPU usage.
        apikey: API Key to authenticate the request.

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


async def service_status(
    request: Request,
    service_name: str,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to monitor a service.**

    **Args:**

        request: Reference to the FastAPI request object.
        service_name: Name of the service to check status.
        apikey: API Key to authenticate the request.

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


async def docker_containers(
    request: Request,
    container_name: str = None,
    get_all: bool = False,
    get_running: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get docker containers' information.**

    **Args:**

        request: Reference to the FastAPI request object.
        container_name: Name of the container to check status.
        get_all: Get all the containers' information.
        get_running: Get running containers' information.
        apikey: API Key to authenticate the request.

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


async def docker_images(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get docker images' information.**

    **Args:**

        request: Reference to the FastAPI request object.
        apikey: API Key to authenticate the request.

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


async def docker_volumes(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get docker volumes' information.**

    **Args:**

        request: Reference to the FastAPI request object.
        apikey: API Key to authenticate the request.

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


async def websocket_endpoint(websocket: WebSocket):
    """Websocket endpoint to fetch live system resource usage.

    Args:
        websocket: Reference to the websocket object.
    """
    await websocket.accept()
    refresh_time = time.time()
    ws_settings = models.WSSettings()
    LOGGER.info("Websocket settings: %s", ws_settings.model_dump_json())
    data = squire.system_resources(ws_settings.cpu_interval)
    while True:
        if websocket.application_state == WebSocketState.CONNECTED:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                if msg.startswith("refresh_interval:"):
                    ws_settings.refresh_interval = int(msg.split(":")[1].strip())
                    LOGGER.info(
                        "Updating refresh interval to %s seconds",
                        ws_settings.refresh_interval,
                    )
                elif msg.startswith("cpu_interval"):
                    ws_settings.cpu_interval = int(msg.split(":")[1].strip())
                    LOGGER.info(
                        "Updating CPU interval to %s seconds", ws_settings.cpu_interval
                    )
                else:
                    LOGGER.error("Invalid WS message received: %s", msg)
                    break
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break
        if time.time() - refresh_time > ws_settings.refresh_interval:
            refresh_time = time.time()
            LOGGER.debug("Fetching new charts")
            data = squire.system_resources(ws_settings.cpu_interval)
        try:
            await websocket.send_json(data)
            await asyncio.sleep(1)
        except WebSocketDisconnect:
            break


def get_all_routes() -> List[APIRoute]:
    """Get all the routes to be added for the API server.

    Returns:
        List[APIRoute]:
        Returns the routes as a list of APIRoute objects.
    """
    dependencies = [
        Depends(dependency=rate_limit.RateLimiter(each_rate_limit).init)
        for each_rate_limit in models.env.rate_limit
    ]
    routes = [
        APIRoute(path="/", endpoint=docs, methods=["GET"], include_in_schema=False),
        APIRoute(
            path="/health", endpoint=health, methods=["GET"], include_in_schema=False
        ),
        APIRoute(
            path="/get-ip",
            endpoint=get_ip,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-cpu",
            endpoint=get_cpu,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-memory",
            endpoint=get_memory,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/service-status",
            endpoint=service_status,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/process-status",
            endpoint=process_status,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-container",
            endpoint=docker_containers,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-image",
            endpoint=docker_images,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-volume",
            endpoint=docker_volumes,
            methods=["GET"],
            dependencies=dependencies,
        ),
    ]
    if all((models.env.remote_execution, models.env.api_secret)):
        routes.append(
            APIRoute(
                path="/run-command",
                endpoint=run_command,
                methods=["POST"],
                dependencies=dependencies,
            )
        )
    return routes
