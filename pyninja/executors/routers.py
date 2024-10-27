import logging
from http import HTTPStatus
from typing import List

from fastapi import Depends
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPBasic, HTTPBearer

from pyninja.modules import exceptions
from pyninja.routes import ipaddr, metrics, namespace, orchestration

LOGGER = logging.getLogger("uvicorn.default")
BASIC_AUTH = HTTPBasic()
BEARER_AUTH = HTTPBearer()


async def docs() -> RedirectResponse:
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


def get_all_routes(dependencies: List[Depends]) -> List[APIRoute]:
    """Get all the routes to be added for the API server.

    Args:
        dependencies: List of dependencies to be added to the routes

    Returns:
        List[APIRoute]:
        Returns the routes as a list of APIRoute objects.
    """
    routes = [
        APIRoute(path="/", endpoint=docs, methods=["GET"], include_in_schema=False),
        APIRoute(
            path="/health", endpoint=health, methods=["GET"], include_in_schema=False
        ),
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
    return routes
