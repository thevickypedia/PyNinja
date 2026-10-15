import asyncio
import logging
from collections.abc import Coroutine
from datetime import datetime
from typing import List, Tuple, Callable

from pyninja.modules import models
from pyninja.scheduled import certs, disks

LOGGER = logging.getLogger("uvicorn.default")


async def runner(coro: Coroutine, now: datetime):
    LOGGER.info("Certificate expiry check scheduled at %s", now.strftime("%c"))
    # Work is about to begin — shield it from cancellation
    work = asyncio.create_task(coro)
    # TODO: Do we really need a callback to handle task completion?
    work.add_done_callback(lambda _: None)
    try:
        await asyncio.shield(work)
    except asyncio.CancelledError:
        LOGGER.warning("Shutdown requested during certificate check, waiting for completion...")
        await work  # Let the coroutine run to completion
        raise  # Then propagate CancelledError to exit the loop


async def scheduler() -> None:
    """Runs scheduler every day at a specified time."""
    scheduled: List[Tuple[str, Callable]] = []
    if models.env.cert_scan:
        scheduled.append((models.env.cert_scan.schedule, certs.monitor_expiry))
    if models.env.disk_health_schedule:
        scheduled.append((models.env.disk_health_schedule, disks.monitor_disk_health))
    if not scheduled:
        LOGGER.info("No scheduled tasks to run")
        return
    LOGGER.info("Starting scheduler")
    last_check = datetime.now().replace(second=0, microsecond=0)
    interval = 10
    while True:
        await asyncio.sleep(interval)
        now = datetime.now().replace(second=0, microsecond=0)
        if now == last_check:
            continue
        last_check = now
        for schedule, func in scheduled:
            hour, minute = map(int, schedule.split(":"))
            if now.hour == hour and now.minute == minute:
                LOGGER.info("Running scheduled task %s at %s", func.__name__, now)
                task = asyncio.create_task(runner(func(), now))
                # TODO: Add a callback to handle task completion
                task.add_done_callback(lambda _: None)
