import asyncio
import json
import logging
import platform
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from http import HTTPStatus

import psutil
from fastapi import Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth, squire
from pyninja.modules import exceptions
from pyninja.monitor import resources

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def get_observability(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    interval: int = 3,
    session_duration: int = 3_600,
    all_services: bool = False,
):
    """**API function to get system metrics via StreamingResponse.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.
        - interval: Sleep interval for streaming.
        - session_duration: Number of seconds for the observability session.
        - all_services: Flag to include all services in the services' metrics.

    **Raises:**

        StreamingResponse:
        Streams system resources information.
    """
    await auth.level_1(request, apikey)
    if session_duration > 10_800:
        raise exceptions.APIResponse(
            status_code=HTTPStatus.BAD_REQUEST.real, detail="Session duration must be less than 3 hours"
        )

    LOGGER.info("Observability session started at: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    LOGGER.info(
        "Streaming metrics until: %s",
        (datetime.now() + timedelta(seconds=session_duration)).strftime("%Y-%m-%d %H:%M:%S"),
    )

    base_payload = {}
    base_payload["ip_info"] = dict(private=squire.private_ip_address(), public=squire.public_ip_address())

    uname = platform.uname()
    base_payload["system"] = uname.system
    base_payload["architecture"] = uname.machine
    base_payload["node"] = uname.node
    base_payload["cores"] = psutil.cpu_count(logical=True)
    base_payload["uptime"] = squire.convert_seconds(
        int(timedelta(seconds=time.time() - psutil.boot_time()).total_seconds())
    )

    architecture = squire.load_architecture()
    if architecture.cpu:
        base_payload["cpu_name"] = architecture.cpu
    if gpus := architecture.gpu:
        base_payload["gpu_name"] = ", ".join([gpu_info.get("model", "") for gpu_info in gpus])
    base_payload["disks_info"] = [
        {k.replace("_", " ").title(): v for k, v in disk.items()} for disk in architecture.disks
    ]

    async def event_stream() -> AsyncGenerator[str]:
        """Streams the system resources as a JSON serializable string."""
        start = time.time()
        while time.time() - start < session_duration:
            beat_payload = await resources.system_resources(all_services=all_services)
            response_payload = {**base_payload, **beat_payload}
            yield json.dumps(response_payload) + "\n"
            await asyncio.sleep(interval)

    return StreamingResponse(event_stream(), media_type="application/json")
