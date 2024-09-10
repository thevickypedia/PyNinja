import logging
import subprocess

from pydantic import FilePath

from . import models

LOGGER = logging.getLogger("uvicorn.default")


def _darwin(lib_path: FilePath) -> str:
    """Get processor information for macOS.

    Args:
        lib_path: Path to the library executable.
    """
    command = [lib_path, "-n", "machdep.cpu.brand_string"]
    return subprocess.check_output(command).decode().strip()


def _linux(lib_path: FilePath) -> str:
    """Get processor information for Linux.

    Args:
        lib_path: Path to the library file.
    """
    with open(lib_path) as file:
        for line in file:
            if "model name" in line:
                return line.split(":")[1].strip()


def _windows(lib_path: FilePath) -> str:
    """Get processor information for Windows.

    Args:
        lib_path: Path to the library file.
    """
    command = f"{lib_path} cpu get name"
    output = subprocess.check_output(command, shell=True).decode()
    return output.strip().split("\n")[1]


def get_name() -> str | None:
    """Get processor information for the host operating system.

    Returns:
        str:
        Returns the processor information as a string.
    """
    os_map = {
        "darwin": _darwin,
        "linux": _linux,
        "windows": _windows,
    }
    try:
        return os_map[models.OPERATING_SYSTEM](models.env.processor_lib)
    except Exception as error:
        LOGGER.error(error)
