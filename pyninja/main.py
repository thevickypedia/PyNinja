import logging
import os

import uvicorn
from fastapi import FastAPI

import pyninja
from pyninja import models, routers, squire

LOGGER = logging.getLogger("uvicorn.default")


def start(**kwargs) -> None:
    """Starter function for the API, which uses uvicorn server as trigger.

    Keyword Args:
        - env_file - Env filepath to load the environment variables.
        - ninja_host - Hostname for the API server.
        - ninja_port - Port number for the API server.
        - workers - Number of workers for the uvicorn server.
        - remote_execution - Boolean flag to enable remote execution.
        - api_secret - Secret access key for running commands on server remotely.
        - database - FilePath to store the auth database that handles the authentication errors.
        - rate_limit - List of dictionaries with `max_requests` and `seconds` to apply as rate limit.
        - apikey - API Key for authentication.
    """
    if env_file := kwargs.get("env_file"):
        models.env = squire.env_loader(env_file)
    elif os.path.isfile(".env"):
        models.env = squire.env_loader(".env")
    else:
        models.env = models.EnvConfig(**kwargs)
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
        version=pyninja.version,
    )
    kwargs = dict(
        host=models.env.ninja_host,
        port=models.env.ninja_port,
        workers=models.env.workers,
        app=app,
    )
    if os.path.isfile("logging.ini"):
        kwargs["log_config"] = os.path.join(os.getcwd(), "logging.ini")
    uvicorn.run(**kwargs)
