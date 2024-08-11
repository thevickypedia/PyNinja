import json
import logging
import os
import pathlib
import subprocess
from typing import Dict, List

import yaml
from pydantic import PositiveFloat, PositiveInt

from pyninja.models import EnvConfig

LOGGER = logging.getLogger("uvicorn.default")


def process_command(
    command: str, timeout: PositiveInt | PositiveFloat
) -> Dict[str, List[str]]:
    """Process the requested command.

    Args:
        command: Command as string.
        timeout: Timeout for the command.

    Returns:
        Dict[str, List[str]]:
        Returns the result with stdout and stderr as key-value pairs.
    """
    process_cmd = subprocess.Popen(
        command,
        shell=True,
        universal_newlines=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = {"stdout": [], "stderr": []}
    stdout, stderr = process_cmd.communicate(timeout=timeout)
    for line in stdout.splitlines():
        LOGGER.info(line.strip())
        result["stdout"].append(line.strip())
    for line in stderr.splitlines():
        LOGGER.error(line.strip())
        result["stderr"].append(line.strip())
    return result


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
