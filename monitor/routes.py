from fastapi import Depends
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute

from monitor.auth import authenticator


async def service_monitor(service_name: str):
    """API function to monitor a service."""
    return service_name


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
