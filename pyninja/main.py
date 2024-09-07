import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from . import exceptions, models, routers, squire, version
from .monitor.config import static

LOGGER = logging.getLogger("uvicorn.default")


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
    if request.url.path == static.login_endpoint:
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
        workers: Number of workers for the uvicorn server.
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
    if all((models.env.remote_execution, models.env.api_secret)):
        LOGGER.info(
            "Creating '%s' to handle authentication errors", models.env.database
        )
        models.database = models.Database(models.env.database)
        models.database.create_table("auth_errors", ["host", "block_until"])
    app = FastAPI(
        routes=routers.get_all_routes(),
        title="PyNinja",
        description="Lightweight OS-agnostic service monitoring API",
        version=version.__version__,
    )
    app.add_exception_handler(
        exc_class_or_status_code=exceptions.RedirectException,
        handler=redirect_exception_handler,
    )
    kwargs = dict(
        host=models.env.ninja_host,
        port=models.env.ninja_port,
        workers=models.env.workers,
        app=app,
    )
    if models.env.log_config:
        kwargs["log_config"] = models.env.log_config
    uvicorn.run(**kwargs)
