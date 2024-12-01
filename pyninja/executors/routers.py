import logging
from http import HTTPStatus
from typing import List

from fastapi import Depends
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.security import HTTPBasic, HTTPBearer

from pyninja.modules import exceptions
from pyninja.monitor import routes as ui
from pyninja.routes import fullaccess, ipaddr, metrics, namespace, orchestration

LOGGER = logging.getLogger("uvicorn.default")
BASIC_AUTH = HTTPBasic()
BEARER_AUTH = HTTPBearer()


async def monitor_redirect() -> RedirectResponse:
    """Redirect to monitor page.

    Returns:
        RedirectResponse:
        Redirects the user to ``/monitor`` page.
    """
    return RedirectResponse("/monitor")


async def docs_redirect() -> RedirectResponse:
    """Redirect to docs page.

    Returns:
        RedirectResponse:
        Redirects the user to ``/docs`` page.
    """
    return RedirectResponse("/docs")


async def health():
    """Health check for PyNinja.

    Returns:
        APIResponse:
        Returns a health check response with status code 200.
    """
    raise exceptions.APIResponse(status_code=HTTPStatus.OK, detail=HTTPStatus.OK.phrase)


def get_api(dependencies: List[Depends]) -> List[APIRoute]:
    """Get all the routes to be added for the API server.

    Args:
        dependencies: List of dependencies to be added to the routes

    Returns:
        List[APIRoute]:
        Returns the routes as a list of APIRoute objects.
    """
    return [
        APIRoute(
            path="/get-ip",
            endpoint=ipaddr.get_ip_address,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-cpu",
            endpoint=metrics.get_cpu_utilization,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-cpu-load",
            endpoint=metrics.get_cpu_load_avg,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-processor",
            endpoint=namespace.get_processor_name,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-memory",
            endpoint=metrics.get_memory_utilization,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-disk",
            endpoint=metrics.get_disk_utilization,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-all-disks",
            endpoint=metrics.get_all_disks,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/service-status",
            endpoint=namespace.get_service_status,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/service-usage",
            endpoint=namespace.get_service_usage,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/process-status",
            endpoint=namespace.get_process_status,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/process-usage",
            endpoint=namespace.get_process_usage,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-container",
            endpoint=orchestration.get_docker_containers,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-image",
            endpoint=orchestration.get_docker_images,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-volume",
            endpoint=orchestration.get_docker_volumes,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-stats",
            endpoint=orchestration.get_docker_stats,
            methods=["GET"],
            dependencies=dependencies,
        ),
    ]


def post_api(dependencies: List[Depends]) -> List[APIRoute]:
    """Get all the routes for FileIO operations and remote execution.

    Args:
        dependencies: List of dependencies to be added to the routes

    Returns:
        List[APIRoute]:
        Returns the routes as a list of APIRoute objects.
    """
    return [
        APIRoute(
            path="/run-command",
            endpoint=fullaccess.run_command,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/list-files",
            endpoint=fullaccess.list_files,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-file",
            endpoint=fullaccess.get_file,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/put-file",
            endpoint=fullaccess.put_file,
            methods=["POST"],
            dependencies=dependencies,
        ),
    ]


def monitoring_ui(dependencies: List[Depends]) -> List[APIRoute | APIWebSocketRoute]:
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
            endpoint=ui.login_endpoint,
            methods=["POST"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIRoute(
            path="/error",
            endpoint=ui.error_endpoint,
            methods=["GET"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIRoute(
            path="/monitor",
            endpoint=ui.monitor_endpoint,
            methods=["GET"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIRoute(
            path="/logout",
            endpoint=ui.logout_endpoint,
            methods=["GET"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIWebSocketRoute(path="/ws/system", endpoint=ui.websocket_endpoint),
    ]
