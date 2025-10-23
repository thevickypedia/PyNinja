import asyncio
import json
import logging
import math
import os
import pathlib
import platform
import re
import secrets
import shutil
import socket
import string
import subprocess
import time
import warnings
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Dict, List

import pyarchitecture
import requests
import yaml
from fastapi import Request

from pyninja.modules import enums, models

LOGGER = logging.getLogger("uvicorn.default")
# noinspection LongLine
IP_REGEX = re.compile(
    r"""^(?:(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])$"""  # noqa: E501
)
YIELD_LINE = lambda inline: inline.rstrip("\n")  # noqa: E731


def public_ip_address() -> str | None:
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


def format_nos(input_: float) -> int | float:
    """Removes ``.0`` float values.

    Args:
        input_: Strings or integers with ``.0`` at the end.

    Returns:
        int | float:
        Int if found, else returns the received float value.
    """
    return int(input_) if isinstance(input_, float) and input_.is_integer() else input_


def format_timedelta(td: timedelta) -> str:
    """Converts timedelta to human-readable format by constructing a formatted string based on non-zero values.

    Args:
        td: Timedelta object.

    See Also:
        Always limits the output to a maximum of two identifiers.

    Examples:
        - 3 days and 1 hour
        - 1 hour and 11 minutes
        - 5 minutes and 23 seconds

    Returns:
        str:
        Human-readable format of timedelta.
    """
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if seconds > 0:
        parts.append(f"{seconds} second{'s' if seconds > 1 else ''}")
    return " and ".join(parts[:2])


def size_converter(byte_size: int | float) -> str:
    """Gets the current memory consumed and converts it to human friendly format.

    Args:
        byte_size: Receives byte size as argument.

    Returns:
        str:
        Converted human-readable size.
    """
    if byte_size:
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        index = int(math.floor(math.log(byte_size, 1024)))
        return f"{format_nos(round(byte_size / pow(1024, index), 2))} {size_name[index]}"
    return "0 B"


async def stream_command(
    request: Request, command: str, shell: bool, timeout: int | float, stream_limit: int | float
) -> AsyncGenerator[str, None]:
    """Async generator to stream command output line-by-line and handle disconnects.

    Args:
        command: Command to be executed.
        timeout: Timeout for the command execution.

    Yields:
        str:
        Lines of output from the command execution.
    """
    try:
        if shell:
            LOGGER.info("Initiating shell command stream: %s", command)
            process = await asyncio.create_subprocess_shell(
                cmd=command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
        else:
            LOGGER.info("Initiating command stream: %s", command)
            process = await asyncio.create_subprocess_exec(
                program=command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
    except Exception as e:
        LOGGER.error("Failed to start subprocess: %s", e)
        yield f"[Failed to start command: {e}]\n"
        return

    output_yielded = False
    try:
        start = time.time()
        while True:
            if await asyncio.shield(request.is_disconnected()):
                LOGGER.warning("Client disconnected. Killing command: %s", command)
                process.kill()
                await process.wait()
                break

            line = await process.stdout.readline()
            if not line:
                break  # EOF

            stripped = YIELD_LINE(line.decode())
            if stripped:
                output_yielded = True
                yield f"{stripped}\n"

            if (time.time() - start) > stream_limit:
                LOGGER.warning("Stream limit reached. Killing command: %s", command)
                process.terminate()
                yield "[Stream limit reached]\n"
                break
        await asyncio.wait_for(process.wait(), timeout=timeout)

    except asyncio.TimeoutError:
        process.kill()
        LOGGER.error("Command timed out and was killed: %s", command)
        yield "[Command timed out]\n"

    except Exception as e:
        process.kill()
        LOGGER.error("Unexpected error during command streaming: %s", e)
        yield f"[Error: {e}]\n"

    finally:
        LOGGER.info("Command execution completed with ouput yielded: %s", output_yielded)
        if not output_yielded:
            yield "[Command finished with no output]\n"


def process_command(command: str, timeout: int | float) -> Dict[str, List[str]]:
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
        line = YIELD_LINE(line)
        LOGGER.info(line)
        result["stdout"].append(line)
    for line in stderr.splitlines():
        LOGGER.error(line)
        result["stderr"].append(line)
    return result


def envfile_loader(filename: str | os.PathLike) -> models.EnvConfig:
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
        return models.EnvConfig(**{k.lower(): v for k, v in env_data.items()})
    elif env_file.suffix.lower() in (".yaml", ".yml"):
        with open(env_file) as stream:
            env_data = yaml.load(stream, yaml.FullLoader)
        return models.EnvConfig(**{k.lower(): v for k, v in env_data.items()})
    elif not env_file.suffix or env_file.suffix.lower() in (
        ".text",
        ".txt",
        "",
    ):
        return models.EnvConfig.from_env_file(env_file)
    else:
        raise ValueError(
            "\n\tUnsupported format for 'env_file', can be one of (.json, .yaml, .yml, .txt, .text, or null)"
        )


def load_env(**kwargs) -> models.EnvConfig:
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
    return models.EnvConfig(**merged_env)


def load_architecture(env: models.EnvConfig) -> models.Architecture:
    """Load architecture details from environment variables.

    Args:
        env: Environment variables.

    Returns:
        Architecture:
        Returns a reference to the ``Architecture`` object.
    """
    return models.Architecture(
        gpu=pyarchitecture.gpu.get_gpu_info(env.gpu_lib),
        cpu=pyarchitecture.cpu.get_cpu_info(env.processor_lib),
        disks=pyarchitecture.disks.get_all_disks(env.disk_lib),
    )


def generate_mfa_token(length: int = 32) -> str:
    """Key generator to create a unique key with an exact length.

    Args:
        length: Exact length of the generated key. Default is 32.

    Returns:
        str:
        Returns a unique key that contains at least one digit, one uppercase letter,
        one lowercase letter, and one safe character.
    """
    if length < 4:
        raise ValueError("Length must be at least 4 to include required character types.")

    # Ensure at least one of each required character
    required_chars = [
        secrets.choice(string.digits),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(["-", "_", ".", "~"]),
    ]

    # Fill the rest with secure random choices from allowed character set
    remaining_length = length - len(required_chars)
    all_chars = string.ascii_letters + string.digits + "-_.~"
    filler = [secrets.choice(all_chars) for _ in range(remaining_length)]

    # Combine all parts and shuffle securely
    token_chars = required_chars + filler
    secrets.SystemRandom().shuffle(token_chars)

    return "".join(token_chars)


def keygen(nbytes: int = 64) -> str:
    """Generate session token from secrets module, so that users are forced to log in when the server restarts.

    Args:
        nbytes: Number of random bytes (nbytes) to generate.

    Returns:
        str:
        Returns a URL safe token.
    """
    return secrets.token_urlsafe(nbytes)


def dynamic_numbers(string: str) -> int | float | None:
    """Convert strings to integer or float dynamically.

    Args:
        string: Number in string format.

    Returns:
        int | float:
        Integer or float value.
    """
    try:
        return int(string)
    except ValueError:
        try:
            return float(string)
        except ValueError:
            return None


def assert_pyudisk() -> None:
    """Ensure disk_report is enabled only for Linux machines and load ``udiskctl`` library."""
    if models.OPERATING_SYSTEM not in (
        enums.OperatingSystem.linux,
        enums.OperatingSystem.darwin,
    ):
        if models.env.disk_report:
            raise ValueError("\n\tdisk_report feature can be enabled only on Linux and macOS machines!")
        return
    try:
        from pyudisk.config import EnvConfig as PyUdiskConfig
    except (ImportError, ModuleNotFoundError):
        if models.env.disk_report:
            raise ValueError(
                "\n\tPyUdisk has not been installed. Use pip install 'PyNinja[extra]' to view disk report metrics."
            )
        return
    # noinspection PyArgumentList
    models.env.smart_lib = models.env.smart_lib or PyUdiskConfig().smart_lib


def assert_tokens() -> None:
    """Ensure at least any of apikey or monitor username and monitor password is set."""
    if models.env.apikey:
        return
    if models.env.monitor_username and models.env.monitor_password:
        return
    raise ValueError(
        "\n\tTo start the API, either an 'apikey' [OR] both 'monitor_username' and 'monitor_password' are required."
    )


def any_mfa_enabled() -> bool:
    """Check if any MFA method is enabled.

    Returns:
        bool:
        Returns True if any MFA method is enabled, else False.
    """
    return (
        any((models.env.gmail_user, models.env.gmail_pass))  # recipient is optional (defaults to gmail_user)
        or any((models.env.ntfy_url, models.env.ntfy_topic))  # ntfy_username and ntfy_password are optional
        or any((models.env.telegram_token, models.env.telegram_chat_id))
        or False
    )


def handle_warnings() -> None:
    """Raises security warnings."""
    try:
        term_size = os.get_terminal_size().columns
    except OSError:
        term_size = 120
    base = "*" * term_size

    if not all((models.env.remote_execution, models.env.api_secret, models.env.apikey)):
        return
    if not any((models.env.authenticator_token, any_mfa_enabled())):
        warnings.warn(
            f"\n{base}"
            "\nThe 'remote_execution' flag is enabled, allowing shell command execution via the API."
            "\nThis feature poses significant security risks and CANNOT be used without MFA."
            f"\n{base}",
            UserWarning,
        )
        models.env.remote_execution = False


def comma_separator(list_: list) -> str:
    """Separates commas using simple ``.join()`` function and includes ``and`` based on input length.

    Args:
        list_: Takes a list of elements as an argument.

    Returns:
        str:
        Comma separated list of elements.
    """
    return ", and ".join([", ".join(list_[:-1]), list_[-1]] if len(list_) > 2 else list_)


def convert_seconds(seconds: int, n_elem: int = 2) -> str:
    """Calculate years, months, days, hours, minutes, and seconds from given input.

    Args:
        seconds: Number of seconds to convert.
        n_elem: Number of elements required from the converted list.

    Returns:
        str:
        Returns a humanized string notion of the number of seconds.
    """
    if not seconds:
        return "0 seconds"
    elif seconds < 60:
        return f"{seconds} seconds"
    elif seconds == 60:
        return "1 minute"

    seconds_in_year = 365 * 24 * 3600  # 365 days in a year
    seconds_in_month = 30 * 24 * 3600  # 30 days in a month

    # Calculate years
    years = seconds // seconds_in_year
    seconds %= seconds_in_year

    # Calculate months
    months = seconds // seconds_in_month
    seconds %= seconds_in_month

    # Calculate days
    days = seconds // (24 * 3600)
    seconds %= 24 * 3600

    # Calculate hours
    hours = seconds // 3600
    seconds %= 3600

    # Calculate minutes
    minutes = seconds // 60
    seconds %= 60

    time_parts = []

    # Add non-zero time components to the list
    if years > 0:
        time_parts.append(f"{years} year{'s' if years > 1 else ''}")
    if months > 0:
        time_parts.append(f"{months} month{'s' if months > 1 else ''}")
    if days > 0:
        time_parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        time_parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        time_parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if seconds > 0:
        time_parts.append(f"{seconds} second{'s' if seconds > 1 else ''}")

    # If only 1 element was requested, return the first element
    if n_elem == 1:
        return time_parts[0]

    # Join the time components into a string with commas
    return comma_separator(time_parts[:n_elem])


def humanize_usage_metrics(**kwargs) -> Dict[str, str]:
    """Convert the usage metrics into human-readable format."""
    percent = round((kwargs["used"] / kwargs["total"]) * 100, 2)
    return {
        "Total": size_converter(kwargs["total"]),
        "Used": size_converter(kwargs["used"]),
        "Free": size_converter(kwargs["free"]),
        "Percent": format_nos(percent),
    }


def total_mountpoints_usage(mountpoints: List[str], as_bytes: bool = False) -> Dict[str, int | str]:
    """Sums up the bytes used on all the mountpoint locations.

    Args:
        mountpoints: List of mountpoints.
        as_bytes: Boolean flag to return the dict as bytes.

    Returns:
        Dict[str, int | str]:
        Returns the usage dictionary as key-value pairs.
    """
    usage_dict = {"total": 0, "used": 0, "free": 0}
    for mountpoint in mountpoints:
        if os.path.exists(mountpoint):
            part_usage = shutil.disk_usage(mountpoint)
            for key in usage_dict:
                usage_dict[key] += getattr(part_usage, key)
        else:
            # Theoretically the path for each mountpoint should exist at least as a symlink
            # Since os.path.exists will work for symlinks, this should catch if there are any discrepancies
            LOGGER.warning("%s doesn't exist!", mountpoint)
    if as_bytes:
        return usage_dict
    return humanize_usage_metrics(**usage_dict)


def mask_sensitive_data(text: str) -> str:
    """Mask sensitive data in the given text.

    Args:
        text: Text to mask sensitive data from.

    Returns:
        str:
        Returns the text with sensitive data masked.
    """
    if models.env.apikey:
        text = text.replace(models.env.apikey, "******")
    if models.env.api_secret:
        text = text.replace(models.env.api_secret, "******")
    if models.env.host_password:
        text = text.replace(models.env.host_password, "******")
    if models.env.monitor_password:
        text = text.replace(models.env.monitor_password, "******")
    if models.env.gmail_pass:
        text = text.replace(models.env.gmail_pass, "******")
    return text


def log_subprocess_error(error: subprocess.CalledProcessError) -> str:
    """Log subprocess error with return code, error reason, and command.

    Args:
        error: Subprocess error object.

    Returns:
        str:
        Returns the error reason as a string.
    """
    output = error.output or ""
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    output = output.strip()

    # fallback to stderr if output is empty
    reason = output or getattr(error, "stderr", "") or ""
    if isinstance(reason, bytes):
        reason = reason.decode("utf-8", errors="replace")
    reason = reason.strip()

    if error.cmd:
        cmd_str = " ".join(map(str, error.cmd))
        cmd_str = mask_sensitive_data(cmd_str)
    else:
        cmd_str = "<unknown command>"
    LOGGER.error("Command failed: %s", cmd_str)
    LOGGER.error("[%s]: %s", error.returncode, reason)
    return reason


def get_mfa_title(include_node: bool) -> str:
    """Generate MFA title with current date and time.

    Args:
        include_node: Boolean flag to include node name in the title.

    Returns:
        str:
        Returns the MFA title.
    """
    if include_node:
        try:
            node = platform.uname().node
        except Exception as error:
            LOGGER.critical(error)
            node = "unknown"
        return f'PyNinja MFA (for: {node}) - {datetime.now().strftime("%B %d, %Y - %I:%M %p")}'
    return f'PyNinja MFA - {datetime.now().strftime("%B %d, %Y - %I:%M %p")}'


class AddProcessName(logging.Filter):
    """Wrapper that overrides ``logging.Filter`` to add ``processName`` to the existing log format.

    >>> AddProcessName

    Args:
        process_name: Takes name of the process to be added as argument.
    """

    def __init__(self, process_name: str):
        """Instantiates super class."""
        self.process_name = process_name
        super().__init__()

    def filter(self, record: logging.LogRecord) -> bool:
        """Overrides the built-in filter record."""
        record.processName = self.process_name
        return True
