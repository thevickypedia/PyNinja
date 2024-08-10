import os
import platform

import uvicorn
from fastapi import FastAPI

from pyninja import router, squire


def start(env_file: str = None) -> None:
    """Starter function for the API, which uses uvicorn server as trigger."""
    squire.env = squire.env_loader(
        env_file or os.environ.get("env_file") or os.environ.get("ENV_FILE") or ".env"
    )
    app = FastAPI(
        routes=router.routes,
        title=f"Service monitor for {platform.uname().node}",
    )
    uvicorn.run(
        host=squire.env.ninja_host,
        port=squire.env.ninja_port,
        workers=squire.env.workers,
        app=app,
    )
