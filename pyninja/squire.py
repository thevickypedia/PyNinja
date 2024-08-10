import json
import os
import pathlib
import socket
from typing import Optional

import yaml
from pydantic import BaseModel, PositiveInt
from pydantic_settings import BaseSettings


class StatusPayload(BaseModel):
    """BaseModel that handles input data for ``StatusPayload``.

    >>> StatusPayload

    """

    service_name: str


class ServiceStatus(BaseModel):
    """Object to load service status with a status code and description.

    >>> ServiceStatus

    """

    pid: int
    status_code: int
    description: str


class EnvConfig(BaseSettings):
    """Object to load environment variables.

    >>> Settings

    """

    ninja_host: str = socket.gethostbyname("localhost") or "0.0.0.0"
    ninja_port: PositiveInt = 8000
    workers: PositiveInt = 1
    apikey: str

    @classmethod
    def from_env_file(cls, env_file: Optional[str]) -> "EnvConfig":
        """Create Settings instance from environment file.

        Args:
            env_file: Name of the env file.

        Returns:
            Settings:
            Loads the ``Settings`` model.
        """
        return cls(_env_file=env_file)

    class Config:
        """Extra configuration for Settings object."""

        extra = "ignore"


def env_loader(filename: str | os.PathLike) -> EnvConfig:
    """Loads environment variables based on filetypes.

    Args:
        filename: Filename from where env vars have to be loaded.

    Returns:
        config.EnvConfig:
        Returns a reference to the ``EnvConfig`` object.
    """
    env_file = pathlib.Path(filename)
    if env_file.suffix.lower() == ".json":
        with open(env_file) as stream:
            env_data = json.load(stream)
        return EnvConfig(**{k.lower(): v for k, v in env_data.items()})
    elif env_file.suffix.lower() in (".yaml", ".yml"):
        with open(env_file) as stream:
            env_data = yaml.load(stream, yaml.FullLoader)
        return EnvConfig(**{k.lower(): v for k, v in env_data.items()})
    elif not env_file.suffix or env_file.suffix.lower() in (
        ".text",
        ".txt",
        "",
    ):
        return EnvConfig.from_env_file(env_file)
    else:
        raise ValueError(
            "\n\tUnsupported format for 'env_file', can be one of (.json, .yaml, .yml, .txt, .text, or null)"
        )


env = EnvConfig
