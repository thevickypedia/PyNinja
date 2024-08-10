import socket
from typing import Optional

from pydantic import BaseModel, PositiveInt
from pydantic_settings import BaseSettings


class ServiceStatus(BaseModel):
    """Object to load service status with a status code and description.

    >>> ServiceStatus

    """

    pid: int
    status_code: int
    description: str


class Settings(BaseSettings):
    """Object to load environment variables.

    >>> Settings

    """

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


settings = Settings
