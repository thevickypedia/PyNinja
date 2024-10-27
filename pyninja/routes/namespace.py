import logging
from http import HTTPStatus
from typing import List

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBearer
from pydantic import PositiveFloat, PositiveInt

from pyninja.executors import auth
from pyninja.features import cpu, operations, process, service
from pyninja.modules import exceptions

LOGGER = logging.getLogger("uvicorn.default")
BASIC_AUTH = HTTPBasic()
BEARER_AUTH = HTTPBearer()


async def get_process_status(
    request: Request,
    process_name: str,
    cpu_interval: PositiveInt | PositiveFloat = 1,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to monitor a process.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - process_name: Name of the process to check status.
        - cpu_interval: Interval in seconds to get the CPU usage.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if response := process.get_process_status(process_name, cpu_interval):
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=response)
    LOGGER.error("%s: 404 - No such process", process_name)
    raise exceptions.APIResponse(
        status_code=404, detail=f"Process {process_name} not found."
    )


async def get_service_usage(
    request: Request,
    service_names: List[str],
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to monitor a service.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - service_names: Name of the service to check status.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    response = await operations.service_monitor(service_names)
    if len(service_names) == 1:
        response = response[0]
        if response.get("PID") == 0000:
            raise exceptions.APIResponse(
                status_code=HTTPStatus.NOT_FOUND.real,
                detail=f"{service_names[0]!r} not found or not running",
            )
    raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=response)


async def get_process_usage(
    request: Request,
    process_names: List[str],
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to monitor a process.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - process_names: Name of the service to check status.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    response = await operations.process_monitor(process_names)
    if len(process_names) == 1:
        response = response[0]
        if response.get("PID") == 0000:
            raise exceptions.APIResponse(
                status_code=HTTPStatus.NOT_FOUND.real,
                detail=f"{process_names[0]!r} not found or not running",
            )
    raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=response)


async def get_service_status(
    request: Request,
    service_name: str,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get the status of a service.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - service_name: Name of the service to check status.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    response = service.get_service_status(service_name)
    LOGGER.info(
        "%s: %d - %s",
        service_name,
        response.status_code,
        response.description,
    )
    raise exceptions.APIResponse(
        status_code=response.status_code, detail=response.description
    )


async def get_processor_name(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get process information.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - process_name: Name of the process to get information.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if processor_info := cpu.get_name():
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real, detail=processor_info
        )
    raise exceptions.APIResponse(
        status_code=HTTPStatus.NOT_FOUND.real,
        detail="Unable to retrieve processor information!",
    )
