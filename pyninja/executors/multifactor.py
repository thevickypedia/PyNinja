import logging
from datetime import datetime
from http import HTTPStatus

import gmailconnector
import jinja2
from fastapi import Request, Response

from pyninja.executors import squire
from pyninja.modules import exceptions, models

LOGGER = logging.getLogger("uvicorn.default")


async def send_mfa(request: Request, response: Response):
    """Work in progress"""
    print(request.client.__dict__.keys())
    mail_obj = gmailconnector.SendEmail(
        gmail_user=models.env.gmail_user, gmail_pass=models.env.gmail_pass
    )
    auth_stat = mail_obj.authenticate
    if not auth_stat.ok:
        LOGGER.error(auth_stat.json())
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real, detail=auth_stat.body
        )
    token = models.keygen()
    rendered = jinja2.Template(models.fileio.mfa_template).render(
        TIMEOUT=squire.convert_seconds(models.env.mfa_timeout),
        ENDPOINT=request.client.host,  # todo: OR something similar
        EMAIL=models.env.recipient,
        TOKEN=token,
    )
    mail_stat = mail_obj.send_email(
        recipient=models.env.recipient,
        sender="PyNinja API",
        subject=f"Multifactor Authenticator - {datetime.now().strftime('%c')}",
        html_body=rendered,
    )
    if mail_stat.ok:
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
