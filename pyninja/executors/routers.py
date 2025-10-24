import logging
from http import HTTPStatus
from typing import List

from fastapi import Depends
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.security import HTTPBearer

from pyninja.executors import squire
from pyninja.modules import enums, exceptions, models
from pyninja.monitor import routes as ui
from pyninja.multifactor import mfa
from pyninja.routes import (
    certificates,
    commands,
    download,
    fullaccess,
    ipaddr,
    metrics,
    namespace,
    orchestration,
    upload,
)

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def monitor_redirect() -> RedirectResponse:
    """Redirect to monitor page.

    Returns:
        RedirectResponse:
        Redirects the user to ``/monitor`` page.
    """
    return RedirectResponse(enums.APIEndpoints.monitor)


async def docs_redirect() -> RedirectResponse:
    """Redirect to docs page.

    Returns:
        RedirectResponse:
        Redirects the user to ``/docs`` page.
    """
    return RedirectResponse(enums.APIEndpoints.docs)


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
    basic_routes = [
        APIRoute(
            path=enums.APIEndpoints.get_ip,
            endpoint=ipaddr.get_ip_address,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_cpu,
            endpoint=metrics.get_cpu_utilization,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_cpu_load,
            endpoint=metrics.get_cpu_load_avg,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_processor,
            endpoint=namespace.get_processor_name,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_memory,
            endpoint=metrics.get_memory_utilization,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_disk_utilization,
            endpoint=metrics.get_disk_utilization,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_all_disks,
            endpoint=metrics.get_all_disks,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_all_services,
            endpoint=namespace.get_all_services,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_service_status,
            endpoint=namespace.get_service_status,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_service_usage,
            endpoint=namespace.get_service_usage,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_process_status,
            endpoint=namespace.get_process_status,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_process_usage,
            endpoint=namespace.get_process_usage,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_docker_containers,
            endpoint=orchestration.get_docker_containers,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_docker_images,
            endpoint=orchestration.get_docker_images,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_docker_volumes,
            endpoint=orchestration.get_docker_volumes,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_docker_stats,
            endpoint=orchestration.get_docker_stats,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_certificates,
            endpoint=certificates.get_certificate,
            methods=["GET"],
            dependencies=dependencies,
        ),
    ]
    # macOS treats applications different from services, so it needs special handling
    if models.OPERATING_SYSTEM == enums.OperatingSystem.darwin:
        basic_routes.append(
            APIRoute(
                path=enums.APIEndpoints.get_all_apps,
                endpoint=namespace.get_all_apps,
                methods=["GET"],
                dependencies=dependencies,
            )
        )
    if squire.any_mfa_enabled():
        basic_routes.insert(
            0,
            APIRoute(
                path=enums.APIEndpoints.get_mfa,
                endpoint=mfa.get_mfa,
                methods=["GET"],
                dependencies=dependencies,
            ),
        )
        basic_routes.insert(
            1,
            APIRoute(
                path=enums.APIEndpoints.delete_mfa,
                endpoint=mfa.delete_mfa,
                methods=["DELETE"],
                dependencies=dependencies,
            ),
        )
    return basic_routes


def post_api(dependencies: List[Depends]) -> List[APIRoute]:
    """Get all the routes for FileIO operations and remote execution.

    Args:
        dependencies: List of dependencies to be added to the routes

    Returns:
        List[APIRoute]:
        Returns the routes as a list of APIRoute objects.
    """
    advanced_routes = [
        APIRoute(
            path=enums.APIEndpoints.run_command,
            endpoint=commands.run_command,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.run_ui,
            endpoint=commands.run_ui,
            methods=["GET"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIRoute(
            path=enums.APIEndpoints.stop_service,
            endpoint=namespace.stop_service,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.start_service,
            endpoint=namespace.start_service,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.restart_service,
            endpoint=namespace.restart_service,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.stop_docker_container,
            endpoint=orchestration.stop_docker_container,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.start_docker_container,
            endpoint=orchestration.start_docker_container,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.list_files,
            endpoint=fullaccess.list_files,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.get_file,
            endpoint=fullaccess.get_file,
            methods=["POST"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.put_file,
            endpoint=fullaccess.put_file,
            methods=["PUT"],
            dependencies=dependencies,
        ),
        APIRoute(
            path=enums.APIEndpoints.delete_content,
            endpoint=fullaccess.delete_content,
            methods=["DELETE"],
            dependencies=dependencies,
        ),
        # Large file upload and download are not included in the docs page
        APIRoute(
            path=enums.APIEndpoints.get_large_file,
            endpoint=download.get_large_file,
            methods=["GET"],
            dependencies=dependencies,
            include_in_schema=False,
            summary="API endpoint to download large files/directories in chunks via streaming response.",
        ),
        APIRoute(
            path=enums.APIEndpoints.put_large_file,
            endpoint=upload.put_large_file,
            methods=["PUT"],
            dependencies=dependencies,
            include_in_schema=False,
            summary="API endpoint to upload large files/directories in chunks via streaming requests.",
        ),
    ]
    # macOS treats applications different from services, so it needs special handling
    if models.OPERATING_SYSTEM == enums.OperatingSystem.darwin:
        advanced_routes.extend(
            [
                APIRoute(
                    path=enums.APIEndpoints.start_app,
                    endpoint=namespace.start_application,
                    methods=["POST"],
                    dependencies=dependencies,
                ),
                APIRoute(
                    path=enums.APIEndpoints.stop_app,
                    endpoint=namespace.stop_application,
                    methods=["POST"],
                    dependencies=dependencies,
                ),
                APIRoute(
                    path=enums.APIEndpoints.restart_app,
                    endpoint=namespace.restart_application,
                    methods=["POST"],
                    dependencies=dependencies,
                ),
            ]
        )
    return advanced_routes


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
            path=enums.APIEndpoints.login,
            endpoint=ui.login_endpoint,
            methods=["POST"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIRoute(
            path=enums.APIEndpoints.error,
            endpoint=ui.error_endpoint,
            methods=["GET"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIRoute(
            path=enums.APIEndpoints.monitor,
            endpoint=ui.monitor_endpoint,
            methods=["GET"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIRoute(
            path=enums.APIEndpoints.logout,
            endpoint=ui.logout_endpoint,
            methods=["GET"],
            dependencies=dependencies,
            include_in_schema=False,
        ),
        APIWebSocketRoute(path=enums.APIEndpoints.ws_system, endpoint=ui.websocket_endpoint),
    ]
