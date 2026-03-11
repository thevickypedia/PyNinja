import asyncio
import logging
import platform
from datetime import datetime, timedelta
from http import HTTPStatus

from pyninja.features import certificates
from pyninja.modules import models
from pyninja.multifactor import gmail, ntfy, telegram

LOGGER = logging.getLogger("uvicorn.default")


async def scheduler() -> None:
    """Schedule the certificate expiry check to run daily at a specified time."""
    while True:
        now = datetime.now()
        hour, minute = map(int, models.env.cert_monitor.split(":"))
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        sleep_seconds = (next_run - now).total_seconds()
        LOGGER.info(
            "Next certificate expiry check scheduled at %s (in %.2f seconds)", next_run.isoformat(), sleep_seconds
        )
        await asyncio.sleep(sleep_seconds)
        await monitor_expiry()


async def notifier(body: str) -> None:
    """Notify the user about expiring certificates."""
    try:
        subject = f"Certificate Expiry Alert from: {platform.uname().node}"
    except Exception as warn:
        LOGGER.warning(warn)
        subject = "Certificate Expiry Alert"
    if models.env.gmail_user and models.env.gmail_pass:
        await gmail.send(subject=subject, body=body)
    if models.env.telegram_token and models.env.telegram_chat_id:
        await telegram.send(message=f"*{subject}*\n\n{body}")
    if models.env.ntfy_url:
        await ntfy.send(title=subject, data=body)


async def monitor_expiry() -> None:
    """Check for certificates expiring within 10 days and log a warning if any are found."""
    response = await certificates.get_all_certificates(raw=False, ws_stream=False)
    if response.status_code == HTTPStatus.OK:
        body = ""
        for certificate in response.certificates:
            if certificate["status"] == "INVALID":
                if certificate["validity"] == 0:
                    body_ = (
                        f"The certificate {certificate['certificate_name']!r} has expired,"
                        f" on {certificate['expiry_date']}"
                    )
                else:
                    body_ = (
                        f"The certificate {certificate['certificate_name']!r} is invalid {certificate['expiry_date']}"
                    )
                LOGGER.critical(body_)
                body += body_ + "\n"
            elif certificate["validity"] <= 10:
                body_ = (
                    f"The certificate {certificate['certificate_name']!r} is expiring soon,"
                    f" on {certificate['expiry_date']} (in {certificate['validity']} days)"
                )
                LOGGER.warning(body_)
                body += body_ + "\n"
            else:
                LOGGER.debug(
                    "The certificate '%s' is valid until %s (in %d days)",
                    certificate["certificate_name"],
                    certificate["expiry_date"],
                    certificate["validity"],
                )
        if body:
            asyncio.create_task(notifier(body))
    else:
        LOGGER.warning("Unsuccessful attempt to check certificate expiry: %s", response.description)
