import logging
from typing import Dict, List

from pyninja.modules import enums, models

from . import linux, macOS, windows

LOGGER = logging.getLogger("uvicorn.default")


def get_all_disks() -> List[Dict[str, str]]:
    """OS-agnostic function to get all disks connected to the host system."""
    os_map = {
        enums.OperatingSystem.darwin: macOS.drive_info,
        enums.OperatingSystem.linux: linux.drive_info,
        enums.OperatingSystem.windows: windows.drive_info,
    }
    try:
        return os_map[models.OPERATING_SYSTEM]()
    except Exception as error:
        LOGGER.error(error)
