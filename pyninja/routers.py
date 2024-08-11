import logging

from fastapi import Depends
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute

from pyninja import auth, exceptions, service, squire

LOGGER = logging.getLogger("uvicorn")


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
        "%s[%d]: %d - %s",
        payload.service_name,
        service_status.pid,
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
        path="/status",
        endpoint=service_status,
        methods=["POST"],
        dependencies=[Depends(auth.authenticator)],
    ),
    APIRoute(path="/", endpoint=docs, methods=["GET"], include_in_schema=False),
]
