import os
from typing import List

from fastapi import Depends
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.templating import Jinja2Templates

from pyninja.monitor import authenticator, config, routes, secure  # noqa: F401

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)


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
        ),
        APIRoute(
            path="/error",
            endpoint=routes.error_endpoint,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/monitor",
            endpoint=routes.monitor_endpoint,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/logout",
            endpoint=routes.logout_endpoint,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIWebSocketRoute(path="/ws/system", endpoint=routes.websocket_endpoint),
    ]