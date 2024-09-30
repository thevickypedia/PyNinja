import logging
from collections.abc import Generator
from typing import Dict, List

import docker
from docker.errors import DockerException

LOGGER = logging.getLogger("uvicorn.default")


def get_container_status(name: str = None) -> str | None:
    """Get container status by name.

    Args:
        name: Name of the container or image used to run the container.

    Returns:
        str:
        Container status as a string.
    """
    try:
        containers = docker.from_env().api.containers()
    except DockerException as error:
        LOGGER.error(error)
        return
    for container in containers:
        if name in container.get("Image") or name in container.get("Names"):
            return (
                f"{container.get('Id')[:12]} - {container.get('Names')} - "
                f"{container.get('State')} - {container.get('Status')}"
            )


def get_running_containers() -> Generator[Dict[str, str]]:
    """Get running containers.

    Yields:
        Dict[str, str]:
        Yields a dictionary of running containers with the corresponding metrics.
    """
    try:
        containers = docker.from_env().api.containers()
    except DockerException as error:
        LOGGER.error(error)
        return []
    for container in containers:
        if container.get("State") == "running":
            yield container


def get_all_containers() -> List[Dict[str, str]] | None:
    """Get all containers and their metrics.

    Returns:
        List[Dict[str, str]]:
        Returns a list of all the containers and their stats.
    """
    try:
        return docker.from_env().api.containers(all=True)
    except DockerException as error:
        LOGGER.error(error)
        return


def get_all_images() -> Dict[str, str] | None:
    """Get all docker images.

    Returns:
        Dict[str, str]:
        Returns a dictionary with image stats.
    """
    try:
        return docker.from_env().api.images(all=True)
    except DockerException as error:
        LOGGER.error(error)
        return


def get_all_volumes() -> Dict[str, str] | None:
    """Get all docker volumes.

    Returns:
        Dict[str, str]:
        Returns a dictionary with list of volume objects.
    """
    try:
        return docker.from_env().api.volumes()
    except DockerException as error:
        LOGGER.error(error)
        return
