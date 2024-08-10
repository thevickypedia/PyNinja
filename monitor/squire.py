import os
import socket
from typing import Optional

from fastapi.exceptions import HTTPException
from pydantic import PositiveInt
from pydantic_settings import BaseSettings


class APIResponse(HTTPException):
    """Custom ``HTTPException`` from ``FastAPI`` to wrap an API response.

    >>> APIResponse

    """


class Settings(BaseSettings):
    """Object to load environment variables."""

    monitor_host: str = socket.gethostbyname("localhost")
    monitor_port: PositiveInt = 8000
    root_password: str
    apikey: str

    @classmethod
    def from_env_file(cls, env_file: Optional[str]) -> "Settings":
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


settings = Settings().from_env_file(
    env_file=os.environ.get("env_file") or os.environ.get("ENV_FILE") or ".env"
)
