import platform
import secrets
from http import HTTPStatus

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.security import HTTPBasicCredentials, HTTPBearer

from monitor.models import APIResponse, settings

SECURITY = HTTPBearer()


async def authenticator(token: HTTPBasicCredentials = Depends(SECURITY)) -> None:
    """Validates the token if mentioned as a dependency.

    Args:
        token: Takes the authorization header token as an argument.

    Raises:
        APIResponse:
        - 401: If authorization is invalid.
    """
    auth = token.model_dump().get("credentials", "")
    if auth.startswith("\\"):
        auth = bytes(auth, "utf-8").decode(encoding="unicode_escape")
    if secrets.compare_digest(auth, settings.apikey):
        return
    raise APIResponse(
        status_code=HTTPStatus.UNAUTHORIZED.real, detail=HTTPStatus.UNAUTHORIZED.phrase
    )


async def service_monitor(service_name: str):
    """API function to monitor a service."""
    return service_name


def start() -> None:
    """Starter function for the API, which uses uvicorn server as trigger."""
    app = FastAPI(
        routes=[
            APIRoute(
                path="/service-monitor",
                endpoint=service_monitor,
                methods=["GET"],
                dependencies=[Depends(authenticator)],
            )
        ],
        title=f"Service monitor for {platform.uname().node}",
    )
    uvicorn.run(host=settings.monitor_host, port=settings.monitor_port, app=app)
