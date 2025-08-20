import logging
from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth
from pyninja.modules import enums, exceptions
from pyninja.multifactor import gmail, ntfy, telegram

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def get_mfa(
    request: Request,
    mfa_option: enums.MFAOptions,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get multifactor authentication code.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code.
    """
    await auth.level_1(request, apikey)
    match mfa_option:
        case enums.MFAOptions.email:
            func = gmail.get_mfa
        case enums.MFAOptions.ntfy:
            func = ntfy.get_mfa
        case enums.MFAOptions.telegram:
            func = telegram.get_mfa
        case _:
            # Handle edge case when passed via curl
            # noinspection PyUnreachableCode
            raise exceptions.APIResponse(
                status_code=HTTPStatus.BAD_REQUEST.real, detail=f"MFA options should be one of: [{enums.MFAOptions}]"
            )
    return await func(request=request, apikey=apikey)
