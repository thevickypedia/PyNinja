import logging
from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBearer

from pyninja.executors import auth
from pyninja.features import dockerized
from pyninja.modules import exceptions
from pyninja.monitor import resources

LOGGER = logging.getLogger("uvicorn.default")
BASIC_AUTH = HTTPBasic()
BEARER_AUTH = HTTPBearer()


async def get_docker_containers(
    request: Request,
    container_name: str = None,
    get_all: bool = False,
    get_running: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get docker containers' information.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - container_name: Name of the container to check status.
        - get_all: Get all the containers' information.
        - get_running: Get running containers' information.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if get_all:
        if all_containers := dockerized.get_all_containers():
            raise exceptions.APIResponse(
                status_code=HTTPStatus.OK.real, detail=all_containers
            )
        raise exceptions.APIResponse(
            status_code=HTTPStatus.NOT_FOUND.real, detail="No containers found!"
        )
    if get_running:
        if running_containers := list(dockerized.get_running_containers()):
            raise exceptions.APIResponse(
                status_code=HTTPStatus.OK.real, detail=running_containers
            )
        raise exceptions.APIResponse(
            status_code=HTTPStatus.NOT_FOUND.real, detail="No running containers found!"
        )
    if container_name:
        if container_status := dockerized.get_container_status(container_name):
            raise exceptions.APIResponse(
                status_code=HTTPStatus.OK.real, detail=container_status
            )
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
            detail="Unable to get container status!",
        )
    raise exceptions.APIResponse(
        status_code=HTTPStatus.BAD_REQUEST.real,
        detail="Either 'container_name' or 'get_all' or 'get_running' should be set",
    )


async def get_docker_images(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get docker images' information.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if images := dockerized.get_all_images():
        LOGGER.info(images)
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=images)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
        detail="Unable to get docker images!",
    )


async def get_docker_volumes(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get docker volumes' information.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if volumes := dockerized.get_all_volumes():
        LOGGER.info(volumes)
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=volumes)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
        detail="Unable to get docker volumes!",
    )


async def get_docker_stats(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get docker-stats for all running containers.**

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
        detail=await resources.get_docker_stats(),
    )
