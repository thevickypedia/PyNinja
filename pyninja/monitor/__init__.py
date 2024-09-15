from typing import List

from fastapi import Depends
from fastapi.routing import APIRoute, APIWebSocketRoute

from . import authenticator, config, routes, secure  # noqa: F401


def get_all_monitor_routes(
    dependencies: List[Depends],
) -> List[APIRoute | APIWebSocketRoute]:
    """Get all the routes for the monitor application.

    Args:
        dependencies: List of dependencies to be injected into the routes.

    Returns:
        List[APIRoute | APIWebSocketRoute]:
        Returns a list of API routes and WebSocket routes.
    """
    return [
        APIRoute(
            path="/login",
            endpoint=routes.login_endpoint,
            methods=["POST"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIRoute(
            path="/error",
            endpoint=routes.error_endpoint,
            methods=["GET"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIRoute(
            path="/monitor",
            endpoint=routes.monitor_endpoint,
            methods=["GET"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIRoute(
            path="/logout",
            endpoint=routes.logout_endpoint,
            methods=["GET"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIWebSocketRoute(path="/ws/system", endpoint=routes.websocket_endpoint),
    ]
