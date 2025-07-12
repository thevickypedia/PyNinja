import logging
from datetime import datetime
from http import HTTPStatus
from threading import Timer

import gmailconnector as gc
import jinja2
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth, squire
from pyninja.modules import cache, exceptions, models

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


@cache.timed_cache(max_age=3_600)
def instantiate_mailer() -> gc.SendEmail:
    """Cached function to instantiate the gmail-connector object.

    Returns:
        gc.SendEmail:
        Returns an instance of the SendEmail class from the gmail-connector module.
    """
    mail_obj = gc.SendEmail(
        gmail_user=models.env.gmail_user, gmail_pass=models.env.gmail_pass
    )
    auth_stat = mail_obj.authenticate
    if not auth_stat.ok:
        LOGGER.error(auth_stat.json())
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real, detail=auth_stat.body
        )
    return mail_obj


def clear_mfa() -> None:
    """Clears the stored MFA token after the timeout period."""
    models.mfa.token = None
    LOGGER.info("Stored MFA token has been cleared")


async def get_mfa(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get multifactor authentication code.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and the public/private IP as response.
    """
    await auth.level_1(request, apikey)
    if not all((models.env.gmail_user, models.env.gmail_pass, models.env.recipient)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
            detail="Gmail user, password, and recipient email must be set in the environment.",
        )
    mail_obj = instantiate_mailer()
    token = models.keygen()
    mail_stat = mail_obj.send_email(
        recipient=models.env.recipient,
        sender="PyNinja API",
        subject=f"Multifactor Authenticator - {datetime.now().strftime('%c')}",
        html_body=jinja2.Template(models.fileio.mfa_template).render(
            TIMEOUT=squire.convert_seconds(models.env.mfa_timeout),
            ENDPOINT=request.client.host,
            EMAIL=models.env.recipient,
            TOKEN=token,
        ),
    )
    if mail_stat.ok:
        models.mfa.token = token
        Timer(interval=models.env.mfa_timeout, function=clear_mfa).start()
        LOGGER.debug(mail_stat.body)
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real,
            detail="Authentication success. OTP has been sent via email.",
        )
    else:
        LOGGER.error(mail_stat.json())
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real, detail=mail_stat.body
        )
