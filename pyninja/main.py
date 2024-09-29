import logging
import os
import pathlib

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.routing import APIRoute

from . import exceptions, models, rate_limit, routes, squire, version
from .monitor import get_all_monitor_routes

BASE_LOGGER = logging.getLogger("BASE_LOGGER")
BASE_LOGGER.setLevel(logging.INFO)
LOGGER = logging.getLogger("uvicorn.default")
PyNinjaAPI = FastAPI(
    title="PyNinja",
    version=version.__version__,
    license_info={"name": "MIT License", "identifier": "MIT"},
)
PyNinjaAPI.__name__ = "PyNinjaAPI"


def get_desc(remote_flag: bool, monitor_flag: bool) -> str:
    """Construct a detailed description for the API docs.

    Args:
        remote_flag: Boolean flag to indicate remote execution state.
        monitor_flag: Boolean flag to indicate monitoring page state.

    Returns:
        str:
        Returns the description as a string.
    """
    if remote_flag:
        remote_fl = "Enabled at <a href='/docs#/default/run_command_run_command_post'>/run-command</a>"
    else:
        remote_fl = "Disabled"
    if monitor_flag:
        monitor_fl = "Enabled at <a href='/monitor'>/monitor</a>"
    else:
        monitor_fl = "Disabled"
    description = "**Lightweight OS-agnostic service monitoring API**"
    description += (
        "\n\nIn addition to monitoring services, processes, and containers,"
        "the PyNinja API provides optional features for executing remote commands "
        "and hosting a real-time system resource monitoring page. 🚀"
    )
    description += "\n\n#### Basic Features"
    description += "\n- <a href='/docs#/default/get_ip_get_ip_get'>/get-ip</a><br>"
    description += "\n- <a href='/docs#/default/get_cpu_get_cpu_get'>/get-cpu</a><br>"
    description += (
        "\n- <a href='/docs#/default/get_memory_get_memory_get'>/get-memory</a><br>"
    )
    description += "\n- <a href='/docs#/default/service_status_service_status_get'>/service-status</a><br>"
    description += "\n- <a href='/docs#/default/process_status_process_status_get'>/process-status</a><br>"
    description += "\n- <a href='/docs#/default/docker_containers_docker_container_get'>/docker-container</a><br>"
    description += "\n- <a href='/docs#/default/docker_images_docker_image_get'>/docker-image</a><br>"
    description += "\n- <a href='/docs#/default/docker_volumes_docker_volume_get'>/docker-volume</a><br>"
    description += "\n\n#### Optional Features"
    description += (
        "\n- <a href='/docs#/default/run_command_run_command_post'>/run-command</a><br>"
    )
    description += (
        "\n- <a href='/docs#/default/monitor_endpoint_monitor_get'>/monitor</a><br>"
    )
    description += "\n\n#### Current State"
    description += f"\n- **Remote Execution:** {remote_fl}"
    description += f"\n- **Monitoring Page:** {monitor_fl}"
    description += "\n\n#### Links"
    description += (
        "\n- <a href='https://pypi.org/project/PyNinja/'>PyPi Repository</a><br>"
    )
    description += (
        "\n- <a href='https://github.com/thevickypedia/PyNinja'>GitHub Homepage</a><br>"
    )
    description += "\n- <a href='https://thevickypedia.github.io/PyNinja/'>Sphinx Documentation</a><br>"
    return description


async def redirect_exception_handler(
    request: Request, exception: exceptions.RedirectException
) -> JSONResponse:
    """Custom exception handler to handle redirect.

    Args:
        request: Takes the ``Request`` object as an argument.
        exception: Takes the ``RedirectException`` object inherited from ``Exception`` as an argument.

    Returns:
        JSONResponse:
        Returns the JSONResponse with content, status code and cookie.
    """
    LOGGER.debug("Exception headers: %s", request.headers)
    LOGGER.debug("Exception cookies: %s", request.cookies)
    if request.url.path == "/login":
        response = JSONResponse(
            content={"redirect_url": exception.location}, status_code=200
        )
    else:
        response = RedirectResponse(url=exception.location)
    if exception.detail:
        response.set_cookie(
            "detail", exception.detail.upper(), httponly=True, samesite="strict"
        )
    return response


def start(**kwargs) -> None:
    """Starter function for the API, which uses uvicorn server as trigger.

    Keyword Args:
        env_file: Env filepath to load the environment variables.
        apikey: API Key for authentication.
        ninja_host: Hostname for the API server.
        ninja_port: Port number for the API server.
        remote_execution: Boolean flag to enable remote execution.
        api_secret: Secret access key for running commands on server remotely.
        monitor_username: Username to authenticate the monitoring page.
        monitor_password: Password to authenticate the monitoring page.
        monitor_session: Session timeout for the monitoring page.
        service_manager: Service manager filepath to handle the service status requests.
        database: FilePath to store the auth database that handles the authentication errors.
        rate_limit: List of dictionaries with ``max_requests`` and ``seconds`` to apply as rate limit.
        log_config: Logging configuration as a dict or a FilePath. Supports .yaml/.yml, .json or .ini formats.
    """
    models.env = squire.load_env(**kwargs)
    dependencies = [
        Depends(dependency=rate_limit.RateLimiter(each_rate_limit).init)
        for each_rate_limit in models.env.rate_limit
    ]
    PyNinjaAPI.routes.extend(routes.get_all_routes(dependencies))
    arg1, arg2 = False, False
    # Conditional endpoint based on remote_execution and api_secret
    if all((models.env.remote_execution, models.env.api_secret)):
        BASE_LOGGER.info(
            "Creating '%s' to handle authentication errors", models.env.database
        )
        models.database = models.Database(models.env.database)
        models.database.create_table("auth_errors", ["host", "block_until"])
        PyNinjaAPI.routes.append(
            APIRoute(
                path="/run-command",
                endpoint=routes.run_command,
                methods=["POST"],
                dependencies=dependencies,
            )
        )
        arg1 = True
    else:
        BASE_LOGGER.warning("Remote execution disabled")
    # Conditional endpoint based on monitor_username and monitor_password
    if all((models.env.monitor_username, models.env.monitor_password)):
        models.env.processes.append(str(os.getpid()))
        PyNinjaAPI.routes.extend(get_all_monitor_routes(dependencies))
        PyNinjaAPI.add_exception_handler(
            exc_class_or_status_code=exceptions.RedirectException,
            handler=redirect_exception_handler,  # noqa: PyTypeChecker
        )
        arg2 = True
    else:
        BASE_LOGGER.warning("Monitoring feature disabled")
    PyNinjaAPI.description = get_desc(arg1, arg2)
    module_name = pathlib.Path(__file__)
    kwargs = dict(
        host=models.env.ninja_host,
        port=models.env.ninja_port,
        app=f"{module_name.parent.stem}.{module_name.stem}:{PyNinjaAPI.__name__}",
    )
    if models.env.log_config:
        kwargs["log_config"] = models.env.log_config
    uvicorn.run(**kwargs)
