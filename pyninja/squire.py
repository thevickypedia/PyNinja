import json
import os
import pathlib
import re
import socket
from typing import Optional

import yaml
from pydantic import BaseModel, PositiveFloat, PositiveInt, field_validator
from pydantic_settings import BaseSettings


def complexity_checker(secret: str) -> None:
    """Verifies the strength of a secret.

    See Also:
        A secret is considered strong if it at least has:

        - 32 characters
        - 1 digit
        - 1 symbol
        - 1 uppercase letter
        - 1 lowercase letter

    Raises:
        AssertionError: When at least 1 of the above conditions fail to match.
    """
    # calculates the length
    assert len(secret) >= 32, f"Minimum secret length is 32, received {len(secret)}"

    # searches for digits
    assert re.search(r"\d", secret), "secret must include an integer"

    # searches for uppercase
    assert re.search(
        r"[A-Z]", secret
    ), "secret must include at least one uppercase letter"

    # searches for lowercase
    assert re.search(
        r"[a-z]", secret
    ), "secret must include at least one lowercase letter"

    # searches for symbols
    assert re.search(
        r"[ !#$%&'()*+,-./[\\\]^_`{|}~" + r'"]', secret
    ), "secret must contain at least one special character"


class Payload(BaseModel):
    """BaseModel that handles input data for ``Payload``.

    >>> Payload

    """

    command: str
    timeout: PositiveInt | PositiveFloat = 3


class ServiceStatus(BaseModel):
    """Object to load service status with a status code and description.

    >>> ServiceStatus

    """

    status_code: int
    description: str


class EnvConfig(BaseSettings):
    """Object to load environment variables.

    >>> Settings

    """

    ninja_host: str = socket.gethostbyname("localhost") or "0.0.0.0"
    ninja_port: PositiveInt = 8000
    workers: PositiveInt = 1
    remote_execution: bool = False
    api_secret: str | None = None
    apikey: str

    # noinspection PyMethodParameters
    @field_validator("api_secret", mode="after")
    def parse_api_secret(cls, value: str | None) -> str | None:
        """Parse API secret to validate complexity.

        Args:
            value: Takes the user input as an argument.

        Returns:
            str:
            Returns the parsed value.
        """
        if value:
            try:
                complexity_checker(value)
            except AssertionError as error:
                raise ValueError(error.__str__())
            return value

    @classmethod
    def from_env_file(cls, env_file: Optional[str]) -> "EnvConfig":
        """Create Settings instance from environment file.

        Args:
            env_file: Name of the env file.

        Returns:
            EnvConfig:
            Loads the ``EnvConfig`` model.
        """
        return cls(_env_file=env_file)

    class Config:
        """Extra configuration for EnvConfig object."""

        extra = "ignore"
        hide_input_in_errors = True


def env_loader(filename: str | os.PathLike) -> EnvConfig:
    """Loads environment variables based on filetypes.

    Args:
        filename: Filename from where env vars have to be loaded.

    Returns:
        EnvConfig:
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
