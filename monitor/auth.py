import secrets
from http import HTTPStatus

from fastapi import Depends
from fastapi.security import HTTPBasicCredentials, HTTPBearer

from monitor.squire import APIResponse, settings

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
