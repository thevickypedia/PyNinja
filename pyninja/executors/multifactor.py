import logging
import time
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

# Minimum time (in seconds) before a new MFA token can be sent
MFA_RESEND_INTERVAL = 120


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


def reset_mfa_code() -> None:
    """Resets the stored MFA token after the timeout period."""
    models.mfa.token = None
    LOGGER.info("Stored MFA token has been cleared")


def clear_timer_list() -> None:
    """Clears the list of active timers."""
    for timer in models.mfa.timers:
        if timer.is_alive():
            LOGGER.info(f"Cancelling timer: {timer.name}")
            timer.cancel()
    models.mfa.timers.clear()
    LOGGER.info("Cleared the list of active timers")


def send_new_mfa() -> bool:
    """Function to check if a new MFA token should be sent."""
    if not models.mfa.token:
        return True
    for timer in models.mfa.timers:
        # Check if the timer is still alive and if it was created within the last 2 minutes
        if timer.is_alive() and int(timer.name) > (
            int(time.time()) - MFA_RESEND_INTERVAL
        ):
            LOGGER.info(
                f"Timer {timer.name!r} is still active, not sending new MFA token."
            )
            return False
    LOGGER.info("No active timers found, sending new MFA token.")
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
        Raises the HTTPStatus object with a status code and the public/private IP as response.
    """
    await auth.level_1(request, apikey)
    if not all((models.env.gmail_user, models.env.gmail_pass, models.env.recipient)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
            detail="Gmail user, password, and recipient email must be set in the environment.",
        )
    if not send_new_mfa():
        LOGGER.info("A recent MFA token is still valid, not sending a new one.")
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real,
            detail="A recent MFA token sent to your email is still valid. "
            "Please check your email (including spam/junk folders) or request a new one after 5 minutes.",
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
        # Start a new timer and clear any existing timers (if alive)
        timer = Timer(interval=models.env.mfa_timeout, function=reset_mfa_code)
        timer.name = str(int(time.time()))
        timer.start()
        clear_timer_list()
        models.mfa.timers.append(timer)
        # Store the token in the models.mfa object
        models.mfa.token = token
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
