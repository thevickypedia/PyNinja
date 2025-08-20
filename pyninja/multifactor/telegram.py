import logging
import time
from datetime import datetime
from http import HTTPStatus
from enum import StrEnum

import gmailconnector as gc
import jinja2
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth, database, squire
from pyninja.modules import cache, enums, exceptions, models
from pyninja.multifactor import gmail, ntfy


LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def get_mfa(
        request: Request,
        apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """Placeholder MFA auth mechanism for Telegram."""
    raise exceptions.APIResponse(status_code=HTTPStatus.IM_A_TEAPOT.real, detail=HTTPStatus.IM_A_TEAPOT.description)
