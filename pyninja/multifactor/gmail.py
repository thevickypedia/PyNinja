import logging
from http import HTTPStatus

import gmailconnector as gc
import jinja2
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth, database, squire
from pyninja.modules import cache, enums, exceptions, models

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


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


async def get_mfa(
    request: Request,
    get_node: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get multifactor authentication code.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - get_node: Boolean flag to include node name in the title.
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
    mail_obj = instantiate_mailer()
    token = squire.generate_mfa_token()
    mail_stat = mail_obj.send_email(
        recipient=models.env.recipient or models.env.gmail_user,
        sender="PyNinja API",
        subject=squire.get_mfa_title(include_node=get_node),
        html_body=jinja2.Template(models.fileio.mfa_template).render(
            TIMEOUT=squire.convert_seconds(models.env.mfa_timeout),
            ENDPOINT=request.client.host,
            EMAIL=models.env.recipient or models.env.gmail_user,
            TOKEN=token,
        ),
    )
    if mail_stat.ok:
        database.update_token(
            token=token,
            table=enums.TableName.mfa_token,
            requester=enums.MFAOptions.email,
            expiry=models.env.mfa_timeout,
        )
        LOGGER.debug(mail_stat.body)
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real,
            detail="Authentication success. OTP has been sent via email.",
        )
    else:
        LOGGER.error(mail_stat.json())
        raise exceptions.APIResponse(status_code=HTTPStatus.SERVICE_UNAVAILABLE.real, detail=mail_stat.body)
