import logging
from http import HTTPStatus

import requests
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth, database, squire
from pyninja.modules import enums, exceptions, models

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


def send_message(
    message: str,
    parse_mode: str | None = "markdown",
) -> requests.Response:
    """Sends a message to the user via Telegram.

    Args:
        message: Message to be sent to the user.
        parse_mode: Parse mode. Defaults to ``markdown``

    Returns:
        Response:
        Response class.
    """
    url = f"https://api.telegram.org/bot{models.env.telegram_token}/sendMessage"
    result = requests.post(
        url=url,
        data={"chat_id": models.env.telegram_chat_id, "text": message, "parse_mode": parse_mode},
        timeout=(5, 60),
    )
    result.raise_for_status()
    return result


async def get_mfa(
    request: Request,
    get_node: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get multifactor authentication code via Telegram.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - get_node: Boolean flag to include node name in the title.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code to indicate MFA delivery.
    """
    await auth.level_1(request, apikey)
    if not all((models.env.telegram_chat_id, models.env.telegram_token)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
            detail="'telegram_token' and 'telegram_chat_id' must be set in the environment.",
        )
    title = squire.get_mfa_title(include_node=get_node)
    token = squire.generate_mfa_token()
    try:
        response = send_message(message=f"*{title}*\n\n```\n{token}\n```")
        LOGGER.debug(response.json())
        database.update_token(
            token=token,
            table=enums.TableName.mfa_token,
            requester=enums.MFAOptions.telegram,
            expiry=models.env.mfa_timeout,
        )
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real,
            detail="Authentication success. OTP has been sent to the requested chat ID.",
        )
    except (requests.RequestException, TimeoutError, ConnectionError) as error:
        # Mask the token in the error message
        error = str(error).replace(models.env.telegram_token, "**********")
        LOGGER.error(error)
        raise exceptions.APIResponse(status_code=HTTPStatus.SERVICE_UNAVAILABLE.real, detail=str(error))
