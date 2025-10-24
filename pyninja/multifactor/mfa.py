import logging
import time
from datetime import datetime
from http import HTTPStatus
from typing import NoReturn

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth, database, squire
from pyninja.modules import enums, exceptions, models
from pyninja.multifactor import gmail, ntfy, telegram

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def send_new_mfa() -> NoReturn | None:
    """Function to check if a new MFA token should be sent."""
    existing_mfa = database.get_token(table=enums.TableName.mfa_token, get_all=True)
    if not existing_mfa:
        return
    _, expiry, requester = existing_mfa
    expiration_generated = expiry - models.env.mfa_timeout
    resend_factor = int(time.time()) - models.env.mfa_resend_delay
    if expiration_generated > resend_factor:
        LOGGER.info(
            f"A recent MFA token generated via {requester} is still valid until "
            f"{datetime.fromtimestamp(expiry).strftime('%c')}, not sending a new one."
        )
        detail = f"A recent MFA token sent to your {requester!r} is still valid."
        if enums.MFAOptions[requester] == enums.MFAOptions.email:
            detail += " Please check your email (including spam/junk folders)."
        detail += f" You can request a new one after {squire.convert_seconds(models.env.mfa_resend_delay, n_elem=1)}."
        detail += f" Time remaining: {squire.convert_seconds(expiration_generated - resend_factor, n_elem=2)}."
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=detail)


async def get_mfa(
    request: Request,
    mfa_option: enums.MFAOptions,
    get_node: bool = True,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get multifactor authentication code.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - get_node: Boolean flag to include node name in the title.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code.
    """
    await auth.level_1(request, apikey)
    await send_new_mfa()
    match mfa_option:
        case enums.MFAOptions.email:
            func = gmail.get_mfa
        case enums.MFAOptions.ntfy:
            func = ntfy.get_mfa
        case enums.MFAOptions.telegram:
            func = telegram.get_mfa
        case _:
            # Handle invalid MFA option
            # noinspection PyUnreachableCode
            raise exceptions.APIResponse(
                status_code=HTTPStatus.BAD_REQUEST.real, detail=f"MFA options should be one of: [{enums.MFAOptions}]"
            )
    return await func(request=request, get_node=get_node, apikey=apikey)


async def delete_mfa(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Delete multifactor authentication code.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code.
    """
    await auth.level_1(request, apikey)
    if not database.get_token(table=enums.TableName.mfa_token):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.NOT_FOUND.real, detail="No active MFA token found to invalidate."
        )
    # Clear existing MFA token
    database.update_token(table=enums.TableName.mfa_token)
    raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail="Active MFA token has been invalidated.")
