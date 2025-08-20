import logging
import time
from datetime import datetime
from http import HTTPStatus

import jinja2
import requests
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth, database, squire
from pyninja.modules import cache, enums, exceptions, models

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()

# Minimum time (in seconds) before a new MFA token can be sent
MFA_RESEND_INTERVAL = 120

async def get_mfa(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get multifactor authentication code via Ntfy.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and the public/private IP as response.
    """
    await auth.level_1(request, apikey)
    if not all([models.env.ntfy_username, models.env.ntfy_password, models.env.ntfy_url, models.env.ntfy_topic]):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
            detail="Ntfy URL, username, password, and topic must be set in the environment.",
        )
    headers = {
        "X-Title": f"Multifactor Authenticator - {datetime.now().strftime('%c')}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    endpoint = f"{models.env.ntfy_url}{models.env.ntfy_topic}"
    # TODO: Ntfy notifications are not be copy-able from mobile phones - so use randomly generated short alpha numeric
    token = models.keygen()
    try:
        response = requests.post(
            url=endpoint,
            auth=(models.env.ntfy_username, models.env.ntfy_password),
            headers=headers,
            data=token,
        )
        response.raise_for_status()
        LOGGER.debug(response.json())
        database.update_token(token=token, table=enums.TableName.mfa_token, expiry=models.env.mfa_timeout)
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real,
            detail="Authentication success. OTP has been sent to the subscribed topic.",
        )
    except (requests.RequestException, TimeoutError, ConnectionError) as error:
        LOGGER.error(error)
        raise exceptions.APIResponse(status_code=HTTPStatus.SERVICE_UNAVAILABLE.real, detail=str(error))
