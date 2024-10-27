import logging
import shutil
from http import HTTPStatus

import psutil
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBearer

from pyninja.executors import auth, squire
from pyninja.features import disks
from pyninja.modules import exceptions

LOGGER = logging.getLogger("uvicorn.default")
BASIC_AUTH = HTTPBasic()
BEARER_AUTH = HTTPBearer()


async def get_cpu_utilization(
    request: Request,
    interval: int | float = 2,
    per_cpu: bool = True,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get the CPU utilization.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - interval: Interval to get the CPU utilization.
        - per_cpu: If True, returns the CPU utilization for each CPU.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and CPU usage as response.
    """
    await auth.level_1(request, apikey)
    if per_cpu:
        cpu_percentages = psutil.cpu_percent(interval=interval, percpu=True)
        usage = {f"cpu{i + 1}": percent for i, percent in enumerate(cpu_percentages)}
    else:
        usage = {"cpu": psutil.cpu_percent(interval=interval, percpu=False)}
    raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=usage)


async def get_memory_utilization(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get memory utilization.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and CPU usage as response.
    """
    await auth.level_1(request, apikey)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.OK.real,
        detail={
            "ram_total": squire.size_converter(psutil.virtual_memory().total),
            "ram_used": squire.size_converter(psutil.virtual_memory().used),
            "ram_usage": psutil.virtual_memory().percent,
            "swap_total": squire.size_converter(psutil.swap_memory().total),
            "swap_used": squire.size_converter(psutil.swap_memory().used),
            "swap_usage": psutil.swap_memory().percent,
        },
    )


async def get_cpu_load_avg(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get the number of processes in the system run queue averaged over the last 1, 5, and 15 minutes respectively.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and CPU usage as response.
    """
    await auth.level_1(request, apikey)
    m1, m5, m15 = psutil.getloadavg() or (None, None, None)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.OK.real,
        detail=dict(m1=m1, m5=m5, m15=m15),
    )


async def get_disk_utilization(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get disk utilization.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and CPU usage as response.
    """
    await auth.level_1(request, apikey)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.OK.real,
        detail={
            k: squire.size_converter(v)
            for k, v in shutil.disk_usage("/")._asdict().items()
        },
    )


async def get_all_disks(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get all disks attached to the host device.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and attached disks as response.
    """
    await auth.level_1(request, apikey)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.OK.real,
        detail=disks.get_all_disks(),
    )
