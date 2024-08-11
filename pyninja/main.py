import logging
import os

import uvicorn
from fastapi import FastAPI

import pyninja
from pyninja import models, routers, squire

LOGGER = logging.getLogger("uvicorn.error")


def start(**kwargs) -> None:
    """Starter function for the API, which uses uvicorn server as trigger.

    Keyword Args:
        env_file: Filepath for the ``.env`` file.
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
