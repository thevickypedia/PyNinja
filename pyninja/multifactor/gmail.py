import logging
import time
from datetime import datetime
from http import HTTPStatus

import gmailconnector as gc
import jinja2
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth, database, squire
from pyninja.modules import cache, enums, exceptions, models

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()

# Minimum time (in seconds) before a new MFA token can be sent
MFA_RESEND_INTERVAL = 120


@cache.timed_cache(max_age=3_600)
def instantiate_mailer() -> gc.SendEmail:
    """Cached function to instantiate the gmail-connector object.

    Returns:
        gc.SendEmail:
        Returns an instance of the SendEmail class from the gmail-connector module.
    """
    mail_obj = gc.SendEmail(gmail_user=models.env.gmail_user, gmail_pass=models.env.gmail_pass)
    auth_stat = mail_obj.authenticate
    if not auth_stat.ok:
        LOGGER.error(auth_stat.json())
        raise exceptions.APIResponse(status_code=HTTPStatus.SERVICE_UNAVAILABLE.real, detail=auth_stat.body)
    return mail_obj


def send_new_mfa() -> bool:
    """Function to check if a new MFA token should be sent.

    Returns:
        bool:
        Returns True if a new MFA token should be sent, False otherwise.
    """
    existing_mfa = database.get_token(table=enums.TableName.mfa_token, include_expiry=True)
    if not existing_mfa:
        return True
    _, expiry = existing_mfa
    expiration_generated = expiry - models.env.mfa_timeout
    if expiration_generated > int(time.time()) - MFA_RESEND_INTERVAL:
        LOGGER.info("MFA token was recently generated, not sending new token.")
        return False
    return True


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
        Raises the HTTPStatus object with a status code to indicate MFA delivery.
    """
    await auth.level_1(request, apikey)
    if not all((models.env.gmail_user, models.env.gmail_pass)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
            detail="'gmail_user' and 'gmail_pass' must be set in the environment.",
        )
    if not send_new_mfa():
        LOGGER.info("A recent MFA token is still valid, not sending a new one.")
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real,
            detail="A recent MFA token sent to your email is still valid. "
            "Please check your email (including spam/junk folders) or request a new one after 5 minutes.",
        )
    mail_obj = instantiate_mailer()
    token = squire.generate_mfa_token()
    mail_stat = mail_obj.send_email(
        recipient=models.env.recipient or models.env.gmail_user,
        sender="PyNinja API",
        subject=f"Multifactor Authenticator - {datetime.now().strftime('%c')}",
        html_body=jinja2.Template(models.fileio.mfa_template).render(
            TIMEOUT=squire.convert_seconds(models.env.mfa_timeout),
            ENDPOINT=request.client.host,
            EMAIL=models.env.recipient or models.env.gmail_user,
            TOKEN=token,
        ),
    )
    if mail_stat.ok:
        database.update_token(token=token, table=enums.TableName.mfa_token, expiry=models.env.mfa_timeout)
        LOGGER.debug(mail_stat.body)
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real,
            detail="Authentication success. OTP has been sent via email.",
        )
    else:
        LOGGER.error(mail_stat.json())
        raise exceptions.APIResponse(status_code=HTTPStatus.SERVICE_UNAVAILABLE.real, detail=mail_stat.body)
