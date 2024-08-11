import logging
import secrets
import subprocess
from http import HTTPStatus
from typing import Optional

from fastapi import Depends, Header, Request
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute

from pyninja import auth, exceptions, process, service, squire

LOGGER = logging.getLogger("uvicorn.error")


# todo: Enable rate-limit and brute-force protection for running commands
async def run_command(
    request: Request, payload: squire.Payload, token: Optional[str] = Header(None)
):
    """**API function to run a command on host machine.**

    **Args:**

        payload: Payload received as request body.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    if squire.env.command_timeout == 0:
        raise exceptions.APIResponse(
            status_code=HTTPStatus.NOT_IMPLEMENTED.real,
            detail="Remote execution has been disabled on the server.",
        )
    if (
        token
        and squire.env.api_secret
        and secrets.compare_digest(token, squire.env.api_secret)
    ):
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
        raise exceptions.APIResponse(
            status_code=HTTPStatus.UNAUTHORIZED.real,
            detail=HTTPStatus.UNAUTHORIZED.phrase,
        )
    process = subprocess.Popen(
        payload.command,
        shell=True,
        universal_newlines=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = {"stdout": [], "stderr": []}
    try:
        stdout, stderr = process.communicate(timeout=squire.env.command_timeout)
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
    if service_status := list(process.get_process_status(process_name)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real, detail=service_status
        )
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
    service_status = service.get_service_status(service_name)
    LOGGER.info(
        "%s: %d - %s",
        service_name,
        service_status.status_code,
        service_status.description,
    )
    raise exceptions.APIResponse(
        status_code=service_status.status_code, detail=service_status.description
    )


async def docs() -> RedirectResponse:
    """Redirect to docs page.

    Returns:
        RedirectResponse:
        Redirects the user to ``/docs`` page.
    """
    return RedirectResponse("/docs")


routes = [
    APIRoute(
        path="/service-status",
        endpoint=service_status,
        methods=["GET"],
        dependencies=[Depends(auth.authenticator)],
    ),
    APIRoute(
        path="/process-status",
        endpoint=process_status,
        methods=["GET"],
        dependencies=[Depends(auth.authenticator)],
    ),
    APIRoute(
        path="/run-command",
        endpoint=run_command,
        methods=["POST"],
        dependencies=[Depends(auth.authenticator)],
    ),
    APIRoute(path="/", endpoint=docs, methods=["GET"], include_in_schema=False),
]
