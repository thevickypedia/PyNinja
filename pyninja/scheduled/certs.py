import platform
import logging
from http import HTTPStatus
from typing import List, Tuple

from pyninja.features import certificates
from pyninja.modules import models
from pyninja.multifactor import gmail, ntfy, telegram

LOGGER = logging.getLogger("uvicorn.default")


def html_body(rows: List[Tuple[str, str, str, str]]) -> str:
    """Construct the HTML body for the certificate expiry report email.

    Args:
        rows: A list of tuples containing certificate details (name, expiry date, status, message).

    Returns:
        str:
        The HTML body for the certificate expiry report email.
    """
    tbody = "\n".join(f"<tr><td>{name}</td><td>{expiry}</td><td>{status}</td></tr>" for name, expiry, status, _ in rows)
    return f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: #f4f4f4;
            }}
        </style>
    </head>
    <body>
        <h2>Certificate Expiry Report</h2>
        <table border="1" cellpadding="6" cellspacing="0">
            <thead>
                <tr>
                    <th>Certificate</th>
                    <th>Expiry Date</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {tbody}
            </tbody>
        </table>
    </body>
    </html>
    """


async def notifier(rows: List[Tuple[str, str, str, str]]) -> None:
    """Notify the user about expiring certificates.

    Args:
        rows: A list of tuples containing certificate details (name, expiry date, status, message).
    """
    try:
        subject = f"Certificate Expiry Alert from {platform.uname().node}"
    except Exception as warn:
        LOGGER.warning(warn)
        subject = "Certificate Expiry Alert PyNinja API"
    if models.env.gmail_user and models.env.gmail_pass:
        await gmail.send(subject=subject, html_body=html_body(rows))
    if models.env.telegram_token and models.env.telegram_chat_id:
        await telegram.send(message="*{}*\n\n{}".format(subject, "\n".join(msg for _, _, _, msg in rows)))
    if models.env.ntfy_url and models.env.ntfy_topic:
        await ntfy.send(subject, f"{len(rows)} certificate(s) expired or nearing expiration")


async def monitor_expiry() -> None:
    """Check for certificates expiring within 10 days and log a warning if any are found."""
    response = await certificates.get_all_certificates(raw=False, ws_stream=False)
    if response.status_code == HTTPStatus.OK:
        rows: List[Tuple[str, str, str, str]] = []
        for cert in response.certificates:
            name = cert["certificate_name"]
            expiry = cert["expiry_date"]
            validity = cert["validity"]
            if validity == 0:
                msg = f"The certificate {name!r} has expired on {expiry}"
                LOGGER.critical(msg)
                rows.append((name, expiry, "Expired", msg))
            elif validity <= models.env.cert_scan.threshold:
                msg = f"The certificate {name!r} is expiring in {validity} days on {expiry}"
                LOGGER.warning(msg)
                rows.append((name, expiry, f"Expiring in {validity} days", msg))
            else:
                LOGGER.debug(
                    "The certificate '%s' is valid until %s (in %d days)",
                    name,
                    expiry,
                    validity,
                )
        if rows:
            await notifier(rows)
    else:
        LOGGER.warning("Unsuccessful attempt to check certificate expiry: %s", response.description)
