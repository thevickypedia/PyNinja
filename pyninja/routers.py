import logging
from http import HTTPStatus

from fastapi import Depends
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute

from pyninja import auth, exceptions, process, service, squire

LOGGER = logging.getLogger("uvicorn.error")


async def process_status(payload: squire.StatusPayload):
    """API function to monitor a process.

    Args:
        payload (StatusPayload): Payload received as request body.

    Raises:
        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    if service_status := list(process.get_process_status(payload.service_name)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real, detail=service_status
        )
    LOGGER.error("%s: 404 - No such process", payload.service_name)
    raise exceptions.APIResponse(
        status_code=404, detail=f"Process {payload.service_name} not found."
    )


async def service_status(payload: squire.StatusPayload):
    """API function to monitor a service.

    Args:
        payload (StatusPayload): Payload received as request body.

    Raises:
        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    service_status = service.get_service_status(payload.service_name)
    LOGGER.info(
        "%s: %d - %s",
        payload.service_name,
        service_status.status_code,
        service_status.description,
    )
    raise exceptions.APIResponse(
        status_code=service_status.status_code, detail=service_status.description
    )


async def docs():
    """Redirect to docs page."""
    return RedirectResponse("/docs")


routes = [
    APIRoute(
        path="/service-status",
        endpoint=service_status,
        methods=["POST"],
        dependencies=[Depends(auth.authenticator)],
    ),
    APIRoute(
        path="/process-status",
        endpoint=process_status,
        methods=["POST"],
        dependencies=[Depends(auth.authenticator)],
    ),
    APIRoute(path="/", endpoint=docs, methods=["GET"], include_in_schema=False),
]
