import platform

import uvicorn
from fastapi import FastAPI

from monitor.routes import routes
from monitor.squire import settings


def start() -> None:
    """Starter function for the API, which uses uvicorn server as trigger."""
    app = FastAPI(
        routes=routes,
        title=f"Service monitor for {platform.uname().node}",
    )
    uvicorn.run(host=settings.monitor_host, port=settings.monitor_port, app=app)
