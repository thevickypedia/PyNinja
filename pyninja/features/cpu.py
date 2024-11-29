import logging
import subprocess

from pyninja.modules import enums, models

LOGGER = logging.getLogger("uvicorn.default")


def _darwin() -> str:
    """Get processor information for macOS."""
    command = [models.env.processor_lib, "-n", "machdep.cpu.brand_string"]
    return subprocess.check_output(command).decode().strip()


def _linux() -> str:
    """Get processor information for Linux."""
    with open(models.env.processor_lib) as file:
        for line in file:
            if "model name" in line:
                return line.split(":")[1].strip()


def _windows() -> str:
    """Get processor information for Windows."""
    command = f"{models.env.processor_lib} cpu get name"
    output = subprocess.check_output(command, shell=True).decode()
    return output.strip().split("\n")[1]


def get_name() -> str | None:
    """Get processor information for the host operating system.

    Returns:
        str:
        Returns the processor information as a string.
    """
    os_map = {
        enums.OperatingSystem.darwin: _darwin,
        enums.OperatingSystem.linux: _linux,
        enums.OperatingSystem.windows: _windows,
    }
    try:
        return os_map[models.OPERATING_SYSTEM]()
    except Exception as error:
        LOGGER.error(error)
