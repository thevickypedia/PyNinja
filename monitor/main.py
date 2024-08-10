import os
import platform

import uvicorn
from fastapi import FastAPI

from monitor import router, squire


def start(env_file: str = None) -> None:
    """Starter function for the API, which uses uvicorn server as trigger."""
    squire.settings = squire.Settings().from_env_file(
        env_file=env_file
        or os.environ.get("env_file")
        or os.environ.get("ENV_FILE")
        or ".env"
    )
    app = FastAPI(
        routes=router.routes,
        title=f"Service monitor for {platform.uname().node}",
    )
    uvicorn.run(
        host=squire.settings.monitor_host, port=squire.settings.monitor_port, app=app
    )
