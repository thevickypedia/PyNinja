import logging
import pathlib

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.routing import APIRoute

from pyninja import version
from pyninja.executors import routers, squire
from pyninja.modules import exceptions, models, rate_limit

BASE_LOGGER = logging.getLogger("BASE_LOGGER")
BASE_LOGGER.setLevel(logging.INFO)
LOGGER = logging.getLogger("uvicorn.default")

PyNinjaAPI = FastAPI(
    title="PyNinja",
    version=version.__version__,
    license_info={"name": "MIT License", "identifier": "MIT"},
)
PyNinjaAPI.__name__ = "PyNinjaAPI"
PyNinjaAPI.routes.append(
    APIRoute(
        path="/health",
        endpoint=routers.health,
        methods=["GET"],
        include_in_schema=False,
    ),
)


def get_desc(get_api: bool, post_api: bool, monitoring_ui: bool) -> str:
    """Construct a detailed description for the API docs.

    Args:
        get_api: Boolean flag to indicate basic API state.
        post_api: Boolean flag to indicate remote execution state.
        monitoring_ui: Boolean flag to indicate monitoring page state.

    Returns:
        str:
        Returns the description as a string.
    """
    basic_fl, remote_fl, monitor_fl = ("Disabled",) * 3
    if get_api:
        basic_fl = "All basic GET calls have been enabled"
    if post_api:
        remote_fl = "Enabled at <a href='/docs#/default/run_command_run_command_post'>/run-command</a>"
    if monitoring_ui:
        monitor_fl = "Enabled at <a href='/monitor'>/monitor</a>"
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
    description += "\n\n#### Additional Features"
    description += (
        "\n- <a href='/docs#/default/run_command_run_command_post'>/run-command</a><br>"
    )
    description += (
        "\n- <a href='/docs#/default/monitor_endpoint_monitor_get'>/monitor</a><br>"
    )
    description += "\n\n#### Current State"
    description += f"\n- **Basic Execution:** {basic_fl}"
    description += f"\n- **Remote Execution:** {remote_fl}"
    description += f"\n- **Monitoring Page:** {monitor_fl}"
    description += "\n\n#### Links"
    description += "\n- <a href='https://pypi.org/project/PyNinja/'>PyPi</a><br>"
    description += (
        "\n- <a href='https://github.com/thevickypedia/PyNinja'>GitHub</a><br>"
    )
    description += (
        "\n- <a href='https://thevickypedia.github.io/PyNinja/'>Runbook</a><br>"
    )
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
    squire.assert_tokens()
    squire.assert_pyudisk()
    squire.handle_warnings()
    dependencies = [
        Depends(dependency=rate_limit.RateLimiter(each_rate_limit).init)
        for each_rate_limit in models.env.rate_limit
    ]
    arg1, arg2, arg3 = False, False, False

    # Conditional endpoints based on 'apikey' value
    if models.env.apikey:
        # Redirect to docs page if apikey is set
        PyNinjaAPI.routes.append(
            APIRoute(
                path="/",
                endpoint=routers.docs_redirect,
                methods=["GET"],
                include_in_schema=False,
            ),
        )
        PyNinjaAPI.routes.extend(routers.get_api(dependencies))
        arg1 = True
    else:
        BASE_LOGGER.warning("Basic API functionality disabled")

    # Conditional endpoints based on 'remote_execution' and 'api_secret' values
    if all((models.env.apikey, models.env.api_secret, models.env.remote_execution)):
        BASE_LOGGER.info(
            "Creating '%s' to handle authentication errors", models.env.database
        )
        models.database = models.Database(models.env.database)
        models.database.create_table("auth_errors", ["host", "block_until"])
        PyNinjaAPI.routes.extend(routers.post_api(dependencies))
        arg2 = True
    else:
        BASE_LOGGER.warning("Remote execution disabled")

    # Conditional endpoints based on 'monitor_username' and 'monitor_password' values
    if all((models.env.monitor_username, models.env.monitor_password)):
        PyNinjaAPI.routes.extend(routers.monitoring_ui(dependencies))
        PyNinjaAPI.add_exception_handler(
            exc_class_or_status_code=exceptions.RedirectException,
            handler=redirect_exception_handler,  # noqa: PyTypeChecker
        )
        if not models.env.apikey:
            # Redirect to /monitor page if apikey is not set
            PyNinjaAPI.routes.append(
                APIRoute(
                    path="/",
                    endpoint=routers.monitor_redirect,
                    methods=["GET"],
                    include_in_schema=False,
                ),
            )
        arg3 = True
    else:
        BASE_LOGGER.warning("Monitoring feature disabled")

    PyNinjaAPI.description = get_desc(arg1, arg2, arg3)
    module_name = pathlib.Path(__file__)
    kwargs = dict(
        host=models.env.ninja_host,
        port=models.env.ninja_port,
        app=f"{module_name.parent.stem}.{module_name.stem}:{PyNinjaAPI.__name__}",
    )
    if models.env.log_config:
        kwargs["log_config"] = models.env.log_config
    uvicorn.run(**kwargs)
