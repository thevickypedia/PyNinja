import json
import logging
import math
import os
import pathlib
import re
import socket
import subprocess
from typing import Dict, List

import psutil
import requests
import yaml
from pydantic import PositiveFloat, PositiveInt

from pyninja.models import EnvConfig

LOGGER = logging.getLogger("uvicorn.default")
IP_REGEX = re.compile(
    r"""^(?:(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])$"""  # noqa: E501
)


def public_ip_address() -> str:
    """Gets public IP address of the host using different endpoints.

    Returns:
        str:
        Public IP address.
    """
    fn1 = lambda fa: fa.text.strip()  # noqa: E731
    fn2 = lambda fa: fa.json()["origin"].strip()  # noqa: E731
    mapping = {
        "https://checkip.amazonaws.com/": fn1,
        "https://api.ipify.org/": fn1,
        "https://ipinfo.io/ip/": fn1,
        "https://v4.ident.me/": fn1,
        "https://httpbin.org/ip": fn2,
        "https://myip.dnsomatic.com/": fn1,
    }
    for url, func in mapping.items():
        try:
            with requests.get(url) as response:
                return IP_REGEX.findall(func(response))[0]
        except (
            requests.RequestException,
            requests.JSONDecodeError,
            re.error,
            IndexError,
        ):
            continue


def private_ip_address() -> str | None:
    """Uses a simple check on network id to see if it is connected to local host or not.

    Returns:
        str:
        Private IP address of host machine.
    """
    socket_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        socket_.connect(("8.8.8.8", 80))
    except OSError:
        return
    ip_address_ = socket_.getsockname()[0]
    socket_.close()
    return ip_address_


def system_resources(cpu_interval: int) -> Dict[str, dict]:
    """Get system resources like CPU, virtual memory and swap memory information.

    Args:
        cpu_interval: Interval in seconds is used to compare CPU times elapsed before and after.

    Returns:
        Dict[str, dict]:
        Returns a nested dictionary.
    """
    return dict(
        cpu_usage=psutil.cpu_percent(interval=cpu_interval, percpu=True),
        memory_info=psutil.virtual_memory()._asdict(),
        swap_info=psutil.swap_memory()._asdict(),
    )


def format_nos(input_: float) -> int | float:
    """Removes ``.0`` float values.

    Args:
        input_: Strings or integers with ``.0`` at the end.

    Returns:
        int | float:
        Int if found, else returns the received float value.
    """
    return int(input_) if isinstance(input_, float) and input_.is_integer() else input_


def size_converter(byte_size: int | float) -> str:
    """Gets the current memory consumed and converts it to human friendly format.

    Args:
        byte_size: Receives byte size as argument.

    Returns:
        str:
        Converted understandable size.
    """
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    index = int(math.floor(math.log(byte_size, 1024)))
    return f"{format_nos(round(byte_size / pow(1024, index), 2))} {size_name[index]}"


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


def envfile_loader(filename: str | os.PathLike) -> EnvConfig:
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


def load_env(**kwargs) -> EnvConfig:
    """Merge env vars from env_file with kwargs, giving priority to kwargs.

    See Also:
        This function allows env vars to be loaded partially from .env files and partially through kwargs.

    Returns:
        EnvConfig:
        Returns a reference to the ``EnvConfig`` object.
    """
    if env_file := kwargs.get("env_file"):
        file_env = envfile_loader(env_file).model_dump()
    elif os.path.isfile(".env"):
        file_env = envfile_loader(".env").model_dump()
    else:
        file_env = {}
    merged_env = {**file_env, **kwargs}
    return EnvConfig(**merged_env)
