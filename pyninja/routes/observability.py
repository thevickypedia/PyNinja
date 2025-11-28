import asyncio
import json
import logging
import platform
import time
from collections.abc import AsyncGenerator
from datetime import timedelta

import psutil
from fastapi import Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth, squire
from pyninja.modules import models
from pyninja.monitor import resources

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def get_observability(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    interval: int = 3,
    all_services: bool = False,
):
    """**API function to get system metrics via StreamingResponse.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.
        - interval: Sleep interval for streaming.

    **Raises:**

        StreamingResponse:
        Streams system resources information.
    """
    await auth.level_1(request, apikey)

    base_payload = {}
    base_payload["ip_info"] = dict(private=squire.private_ip_address(), public=squire.public_ip_address())

    uname = platform.uname()
    base_payload["system"] = uname.system
    base_payload["architecture"] = uname.machine
    base_payload["node"] = uname.node
    base_payload["cores"] = psutil.cpu_count(logical=True)
    base_payload["uptime"] = squire.format_timedelta(timedelta(seconds=time.time() - psutil.boot_time()))

    if models.architecture.cpu:
        base_payload["cpu_name"] = models.architecture.cpu
    if gpus := models.architecture.gpu:
        base_payload["gpu_name"] = ", ".join([gpu_info.get("model") for gpu_info in gpus])
    base_payload["disks_info"] = [
        {k.replace("_", " ").title(): v for k, v in disk.items()} for disk in models.architecture.disks
    ]

    async def event_stream() -> AsyncGenerator[str]:
        """Streams the system resources as a JSON serializable string."""
        start = time.time()
        while time.time() - start < models.env.observability_session:
            beat_payload = await resources.system_resources(all_services=all_services)
            response_payload = {**base_payload, **beat_payload}
            yield json.dumps(response_payload) + "\n"
            await asyncio.sleep(interval)

    return StreamingResponse(event_stream(), media_type="application/json")
