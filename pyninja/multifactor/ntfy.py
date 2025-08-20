import logging
from datetime import datetime
from http import HTTPStatus

import requests
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth, database, squire
from pyninja.modules import enums, exceptions, models

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
        Raises the HTTPStatus object with a status code to indicate MFA delivery.
    """
    await auth.level_1(request, apikey)
    if not all((models.env.ntfy_url, models.env.ntfy_topic)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
            detail="Ntfy URL, username, password, and topic must be set in the environment.",
        )
    session = requests.Session()
    session.headers = {
        "X-Title": f"PyNinja MFA - {datetime.now().strftime('%c')}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    if models.env.ntfy_username and models.env.ntfy_password:
        session.auth = (models.env.ntfy_username, models.env.ntfy_password)
    endpoint = f"{models.env.ntfy_url}{models.env.ntfy_topic}"
    token = squire.generate_mfa_token(length=8)
    try:
        response = session.post(url=endpoint, data=token)
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
