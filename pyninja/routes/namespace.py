import logging
from http import HTTPStatus
from typing import Optional

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import PositiveFloat, PositiveInt

from pyninja.executors import auth
from pyninja.features import operations, process, service
from pyninja.modules import exceptions, models

LOGGER = logging.getLogger("uvicorn.default")
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
    service_name: str,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to monitor a service.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - process_name: Comma separated list of service names.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    service_names = [sname.strip() for sname in service_name.split(",")]
    response = await operations.service_monitor(service_names)
    if len(service_names) == 1:
        response = response[0]
        if response.get("PID") == 0000 or response.get("PID") == 0:
            raise exceptions.APIResponse(
                status_code=HTTPStatus.NOT_FOUND.real,
                detail=f"{service_names[0]!r} not found or not running",
            )
    raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=response)


async def get_process_usage(
    request: Request,
    process_name: str,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to monitor a process.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - process_name: Comma separated list of process names.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    process_names = [pname.strip() for pname in process_name.split(",")]
    if response := await operations.process_monitor(process_names):
        if len(process_names) == 1:
            response = response[0]
            if response.get("PID") == 0000 or response.get("PID") == 0:
                raise exceptions.APIResponse(
                    status_code=HTTPStatus.NOT_FOUND.real,
                    detail=f"{process_names[0]!r} not found or not running",
                )
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=response)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.NOT_FOUND.real,
        detail=f"Process names not found: {', '.join(process_names)}",
    )


async def get_all_services(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get a list of all the services.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if response := list(service.get_all_services()):
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=response)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR.real,
        detail="Failed to retrieve service list",
    )


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
    LOGGER.debug(
        "%s: %d - %s",
        service_name,
        response.status_code,
        response.description,
    )
    raise exceptions.APIResponse(
        status_code=response.status_code, detail=response.description
    )


async def stop_service(
    request: Request,
    service_name: str,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """**API function to stop a service.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - service_name: Name of the service to check status.
        - apikey: API Key to authenticate the request.
        - token: API secret to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_2(request, apikey, token)
    response = service.stop_service(service_name)
    LOGGER.info(
        "%s: %d - %s",
        service_name,
        response.status_code,
        response.description,
    )
    raise exceptions.APIResponse(
        status_code=response.status_code, detail=response.description
    )


async def start_service(
    request: Request,
    service_name: str,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """**API function to start a service.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - service_name: Name of the service to check status.
        - apikey: API Key to authenticate the request.
        - token: API secret to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_2(request, apikey, token)
    response = service.start_service(service_name)
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
    if models.architecture.cpu:
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real, detail=models.architecture.cpu
        )
    raise exceptions.APIResponse(
        status_code=HTTPStatus.NOT_FOUND.real,
        detail="Unable to retrieve processor information!",
    )
