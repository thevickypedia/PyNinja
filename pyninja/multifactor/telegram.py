import logging
from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.modules import exceptions

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def get_mfa(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """Placeholder MFA auth mechanism for Telegram."""
    raise exceptions.APIResponse(status_code=HTTPStatus.IM_A_TEAPOT.real, detail=HTTPStatus.IM_A_TEAPOT.description)
