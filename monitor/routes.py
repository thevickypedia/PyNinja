import logging
from http import HTTPStatus

from fastapi import Depends
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute

from monitor.auth import authenticator
from monitor.exceptions import APIResponse, ServiceNotFound
from monitor.service import get_service_status

LOGGER = logging.getLogger("uvicorn.error")


async def service_monitor(service_name: str):
    """API function to monitor a service."""
    try:
        service_status = get_service_status(service_name)
    except ServiceNotFound as error:
        LOGGER.error(error)
        raise APIResponse(status_code=HTTPStatus.NOT_FOUND.real, detail=error.__str__())
    LOGGER.info(
        "%s[%d]: %d - %s",
        service_name,
        service_status.pid,
        service_status.status_code,
        service_status.description,
    )
    raise APIResponse(
        status_code=service_status.status_code, detail=service_status.description
    )


async def docs():
    """Redirect to docs page."""
    return RedirectResponse("/docs")


routes = [
    APIRoute(
        path="/service-monitor",
        endpoint=service_monitor,
        methods=["GET"],
        dependencies=[Depends(authenticator)],
    ),
    APIRoute(path="/", endpoint=docs, methods=["GET"], include_in_schema=False),
]
