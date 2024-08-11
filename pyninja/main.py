import os

import uvicorn
from fastapi import FastAPI

from pyninja import routers, squire

version = "0.0.0"


def start(env_file: str = None) -> None:
    """Starter function for the API, which uses uvicorn server as trigger.

    Args:
        env_file: Filepath for the ``.env`` file.
    """
    squire.env = squire.env_loader(
        env_file or os.environ.get("env_file") or os.environ.get("ENV_FILE") or ".env"
    )
    app = FastAPI(
        routes=routers.routes,
        title="PyNinja",
        description="Light weight OS agnostic service monitoring API",
        version=version,
    )
    kwargs = dict(
        host=squire.env.ninja_host,
        port=squire.env.ninja_port,
        workers=squire.env.workers,
        app=app,
    )
    if os.path.isfile("logging.ini"):
        kwargs["log_config"] = os.path.join(os.getcwd(), "logging.ini")
    uvicorn.run(**kwargs)
