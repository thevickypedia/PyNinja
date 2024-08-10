import logging

from fastapi import Depends
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute

from monitor import auth, exceptions, service

logging.getLogger("uvicorn.access").disabled = True
LOGGER = logging.getLogger("uvicorn.error")


async def service_monitor(service_name: str):
    """API function to monitor a service."""
    service_status = service.get_service_status(service_name)
    LOGGER.info(
        "%s[%d]: %d - %s",
        service_name,
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
        path="/service-monitor",
        endpoint=service_monitor,
        methods=["GET"],
        dependencies=[Depends(auth.authenticator)],
    ),
    APIRoute(path="/", endpoint=docs, methods=["GET"], include_in_schema=False),
]
