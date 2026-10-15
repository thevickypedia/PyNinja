import html
import logging
import platform
from collections.abc import AsyncGenerator
from typing import Any, Dict, List
import pyudisk

from pyudisk.models import udisk, smartctl
from pyudisk.util import k2f

from pyninja.modules import models
from pyninja.multifactor import gmail, ntfy, telegram

LOGGER = logging.getLogger("uvicorn.default")


async def smart_reasons(drive: smartctl.Disk) -> AsyncGenerator[str]:
    health = drive.nvme_smart_health_information_log
    smart_status = drive.smart_status

    if smart_status:
        # A failed overall SMART health check.
        if smart_status.passed is False:
            yield "SMART overall health check failed"

        if smart_status.nvme and smart_status.nvme.value:
            yield "NVMe critical health status reported"

    if not health:
        return

    # NVMe critical_warning is a bit field; any set bit is significant.
    if health.critical_warning:
        yield f"NVMe critical warning: {health.critical_warning:#x}"

    if health.media_errors:
        yield f"NVMe media errors: {health.media_errors}"

    if (
        health.available_spare
        and health.available_spare_threshold
        and health.available_spare <= health.available_spare_threshold
    ):
        yield (
            f"Available spare capacity ({health.available_spare}%) is at or "
            f"below threshold ({health.available_spare_threshold}%)"
        )

    if health.percentage_used >= 100:
        yield (f"Estimated NVMe endurance consumed: {health.percentage_used}%")

    # A nonzero exit status alone is not proof of drive failure.
    # For example, an unsupported external USB bridge can prevent
    # SMART access even when the underlying disk is healthy.


async def udisk_reasons(drive: udisk.Disk) -> AsyncGenerator[str]:
    attrs = drive.Attributes
    if not attrs:
        return

    # Explicit SMART failure indicators.
    if attrs.SmartFailing:
        yield "SMART reports imminent failure"

    if (attrs.SmartNumAttributesFailing or 0) > 0:
        yield "SMART attributes are currently failing"

    if (attrs.SmartNumBadSectors or 0) > 0:
        yield "SMART reports bad sectors"

    if (attrs.SmartNumAttributesFailedInThePast or 0) > 0:
        yield "SMART attributes failed in the past"

    # A failed self-test is a failure indicator
    selftest = str(attrs.SmartSelftestStatus or "").lower()
    if selftest in ("failed", "failure", "fatal"):
        yield f"SMART self-test failed: {selftest}"

    # UDisks reports temperature in Kelvin in the supplied data.
    if attrs.SmartTemperature:
        temp_f = k2f(attrs.SmartTemperature)
        if temp_f >= 158:
            yield (f"Critical operating temperature: {temp_f:.1f} F")


async def get_vulnerable_disks() -> AsyncGenerator[Dict[str, Any]]:
    """Yield disks with deterministic indicators of possible failure.

    Only disks with positive failure indicators are yielded.
    Missing or inaccessible SMART data is not itself a failure.

    Returns:
        Dict[str, Any]:
        Generator of disk dictionaries with failure indicators.
    """
    for drive in pyudisk.smart_metrics():
        if isinstance(drive, udisk.Disk):
            name = drive.id
            model = drive.model
            reasons: list[str] = []
            async for reason in udisk_reasons(drive):
                reasons.append(reason)
        elif isinstance(drive, smartctl.Disk):
            name = drive.device.name
            model = drive.model_name
            reasons: list[str] = []
            async for reason in smart_reasons(drive):
                reasons.append(reason)
        else:
            continue
        if reasons:
            yield {
                "device": name,
                "model": model,
                "reasons": reasons,
            }


def html_body(rows: List[Dict[str, str | List[str]]]) -> str:
    """Construct the HTML body for the disk health alert email.

    Args:
        rows: A list of dictionaries containing disk details (device, model, reasons).

    Returns:
        str: The HTML body for the disk health alert email.
    """
    devices = "\n".join(
        f"""
        <div>
            <h3>{html.escape(str(row.get('device', 'Unknown device')))}</h3>
            <h3>{html.escape(str(row.get('model', 'Unknown model')))}</h3>
            <ul>
                {"".join(
            f"<li>{html.escape(str(reason))}</li>"
            for reason in row.get("reasons", [])
        )}
            </ul>
        </div>
        """
        for row in rows
    )

    return f"""
    <html>
    <head></head>
    <body>
        <h2>Disk Health Alert</h2>
        {devices}
    </body>
    </html>
    """


async def notifier(report: List[Dict[str, Any]]) -> None:
    """Notify the user about expiring certificates.

    Args:
        report: A list of dictionaries containing disk health details (device, model, reasons).
    """
    try:
        subject = f"Disk Health Alert from {platform.uname().node}"
    except Exception as warn:
        LOGGER.warning(warn)
        subject = "Disk Health Alert PyNinja API"
    if models.env.gmail_user and models.env.gmail_pass:
        await gmail.send(subject=subject, html_body=html_body(report))
    if models.env.telegram_token and models.env.telegram_chat_id:
        await telegram.send(
            message="*{}*\n\n{}".format(
                subject,
                "\n\n".join(
                    f"*{row.get('device', 'Unknown device')}* — {row.get('model', 'Unknown model')}\n"
                    + "\n".join(f"• {reason}" for reason in row.get("reasons", []))
                    for row in report
                ),
            )
        )
    if models.env.ntfy_url and models.env.ntfy_topic:
        await ntfy.send(subject, f"{len(report)} disks at risk\n" + "\n".join(row["model"] for row in report))


async def monitor_disk_health() -> None:
    if vulnerable := [item async for item in get_vulnerable_disks()]:
        LOGGER.warning("Vulnerable disks found: %s", vulnerable)
        await notifier(report=vulnerable)
    else:
        LOGGER.info("No vulnerable disks found.")
