import logging
import subprocess
from http import HTTPStatus
from typing import List, Optional

from fastapi import Depends, Header, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import PositiveFloat, PositiveInt

from pyninja import auth, exceptions, models, process, rate_limit, service, squire

LOGGER = logging.getLogger("uvicorn.default")
security = HTTPBearer()


async def run_command(
    request: Request,
    payload: models.Payload,
    apikey: HTTPAuthorizationCredentials = Depends(security),
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
    apikey: HTTPAuthorizationCredentials = Depends(security),
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
    apikey: HTTPAuthorizationCredentials = Depends(security),
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


async def docs() -> RedirectResponse:
    """Redirect to docs page.

    Returns:
        RedirectResponse:
        Redirects the user to ``/docs`` page.
    """
    return RedirectResponse("/docs")


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
