import logging
import secrets
import subprocess
from datetime import datetime
from http import HTTPStatus
from typing import List, Optional

from fastapi import Depends, Header, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute

from pyninja import auth, database, exceptions, models, process, rate_limit, service

LOGGER = logging.getLogger("uvicorn.error")


async def run_command(
        request: Request, payload: models.Payload, token: Optional[str] = Header(None)
):
    """**API function to run a command on host machine.**

    **Args:**

        payload: Payload received as request body.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    # todo: remove dependency authentication and convert it to condition match
    #   add failed auth to handle_auth_errors
    # placeholder list, to avoid a DB search for every request
    if request.client.host in models.session.forbid:
        # Get timestamp until which the host has to be forbidden
        if (
                timestamp := database.get_record(request.client.host)
        ) and timestamp > auth.EPOCH():
            LOGGER.warning(
                "%s is forbidden until %s due to repeated login failures",
                request.client.host,
                datetime.fromtimestamp(timestamp).strftime("%c"),
            )
            raise exceptions.APIResponse(
                status_code=HTTPStatus.FORBIDDEN.value,
                detail=f"{request.client.host!r} is not allowed",
            )
    if not all((models.env.remote_execution, models.env.api_secret)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.NOT_IMPLEMENTED.real,
            detail="Remote execution has been disabled on the server.",
        )
    if token and secrets.compare_digest(token, models.env.api_secret):
        LOGGER.info(
            "Command request '%s' received from client-host: %s, host-header: %s, x-fwd-host: %s",
            payload.command,
            request.client.host,
            request.headers.get("host"),
            request.headers.get("x-forwarded-host"),
        )
        if user_agent := request.headers.get("user-agent"):
            LOGGER.info("User agent: %s", user_agent)
    else:
        await auth.handle_auth_error(request)
        raise exceptions.APIResponse(
            status_code=HTTPStatus.UNAUTHORIZED.real,
            detail=HTTPStatus.UNAUTHORIZED.phrase,
        )
    process_cmd = subprocess.Popen(
        payload.command,
        shell=True,
        universal_newlines=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = {"stdout": [], "stderr": []}
    try:
        stdout, stderr = process_cmd.communicate(timeout=payload.timeout)
    except subprocess.TimeoutExpired as warn:
        LOGGER.warning(warn)
        raise exceptions.APIResponse(
            status_code=HTTPStatus.REQUEST_TIMEOUT, detail=warn.__str__()
        )
    for line in stdout.splitlines():
        LOGGER.info(line.strip())
        output["stdout"].append(line.strip())
    for line in stderr.splitlines():
        LOGGER.error(line.strip())
        output["stderr"].append(line.strip())
    raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=output)


async def process_status(process_name: str):
    """**API function to monitor a process.**

    **Args:**

        process_name: Name of the process to check status.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    if response := list(process.get_process_status(process_name)):
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=response)
    LOGGER.error("%s: 404 - No such process", process_name)
    raise exceptions.APIResponse(
        status_code=404, detail=f"Process {process_name} not found."
    )


async def service_status(service_name: str):
    """**API function to monitor a service.**

    **Args:**

        service_name: Name of the service to check status.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
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
    APIRoute(path="/", endpoint=docs, methods=["GET"], include_in_schema=False)
    dependencies = [Depends(auth.authenticator)]
    for each_rate_limit in models.env.rate_limit:
        LOGGER.info("Adding rate limit: %s", each_rate_limit)
        dependencies.append(
            Depends(dependency=rate_limit.RateLimiter(each_rate_limit).init)
        )
    routes = [
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
