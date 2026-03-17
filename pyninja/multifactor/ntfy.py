import logging
from http import HTTPStatus

import requests
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth, database, squire
from pyninja.modules import enums, exceptions, models

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def send(title: str, data: str) -> bool:
    """Function to send a notification via Ntfy.

    Args:
        title: Ntfy notification title.
        data: Data to be sent in the notification body.

    Returns:
        bool:
        Returns True if the notification was sent successfully, False otherwise.
    """
    session = requests.Session()
    session.headers = {
        "X-Title": title,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    if models.env.ntfy_username and models.env.ntfy_password:
        session.auth = (models.env.ntfy_username, models.env.ntfy_password)
    endpoint = f"{models.env.ntfy_url}{models.env.ntfy_topic}"
    try:
        response = session.post(url=endpoint, data=data, timeout=(5, 10))
        response.raise_for_status()
        LOGGER.debug(response.json())
        return True
    except Exception as error:
        LOGGER.error(error)
        return False


async def get_mfa(
    request: Request,
    get_node: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get multifactor authentication code via Ntfy.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - get_node: Boolean flag to include node name in the title.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code to indicate MFA delivery.
    """
    await auth.level_1(request, apikey)
    if not all((models.env.ntfy_url, models.env.ntfy_topic)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
            detail="'ntfy_url', and 'ntfy_topic' must be set in the environment.",
        )
    token = squire.generate_mfa_token(length=8)
    response = await send(title=squire.get_mfa_title(include_node=get_node), data=token)
    if response:
        database.update_token(
            token=token, table=enums.TableName.mfa_token, requester=enums.MFAOptions.ntfy, expiry=models.env.mfa_timeout
        )
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real,
            detail="Authentication success. OTP has been sent to the subscribed topic.",
        )
    else:
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
            detail="Failed to send OTP via Ntfy. Please check the logs for more details.",
        )
