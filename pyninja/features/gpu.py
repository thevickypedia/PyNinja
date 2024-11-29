import json
import logging
import subprocess
from typing import Dict, List, Optional

from pyninja.modules import models

LOGGER = logging.getLogger("uvicorn.default")


def _darwin() -> Optional[List[Dict[str, str]]]:
    """Get GPU model and vendor information for Linux operating system.

    Returns:
        List[Dict[str, str]]:
        Returns a list of GPU model and vendor information.
    """
    result = subprocess.run(
        [models.env.gpu_lib, "SPDisplaysDataType", "-json"],
        capture_output=True,
        text=True,
    )
    if result.stderr:
        LOGGER.debug(result.stderr)
        return
    displays = json.loads(result.stdout).get("SPDisplaysDataType", [])
    gpu_info = []
    for display in displays:
        if "sppci_model" in display.keys():
            gpu_info.append(
                dict(
                    model=display.get("sppci_model"),
                    cores=display.get("sppci_cores", "N/A"),
                    memory=display.get(
                        "sppci_vram", display.get("spdisplays_vram", "N/A")
                    ),
                    vendor=display.get("sppci_vendor", "N/A"),
                )
            )
    return gpu_info


def _linux() -> Optional[List[Dict[str, str]]]:
    """Get GPU model and vendor information for Linux operating system.

    Returns:
        List[Dict[str, str]]:
        Returns a list of GPU model and vendor information.
    """
    result = subprocess.run(
        [models.env.gpu_lib],
        capture_output=True,
        text=True,
    )
    if result.stderr:
        LOGGER.debug(result.stderr)
        return
    gpus = result.stdout.splitlines()
    gpu_info = []
    for line in gpus:
        if "VGA" in line:
            gpu = line.split(":")[-1].strip()
        else:
            continue
        gpu_info.append(
            dict(
                model=gpu.split(":")[-1].strip(),
            )
        )
    return gpu_info


def _windows() -> Optional[List[Dict[str, str]]]:
    """Get GPU model and vendor information for Windows operating system.

    Returns:
        List[Dict[str, str]]:
        Returns a list of GPU model and vendor information.
    """
    result = subprocess.run(
        [
            models.env.gpu_lib,
            "path",
            "win32_videocontroller",
            "get",
            "Name,AdapterCompatibility",
            "/format:csv",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    if result.stderr:
        LOGGER.debug(result.stderr)
        return
    gpus_raw = [line for line in result.stdout.splitlines() if line.strip()]
    try:
        keys = (
            gpus_raw[0]
            .replace("Node", "node")
            .replace("AdapterCompatibility", "vendor")
            .replace("Name", "model")
            .split(",")
        )
        values = "".join(gpus_raw[1:]).split(",")
    except ValueError as error:
        LOGGER.debug(error)
        return
    if len(values) >= len(keys):
        result = []
        for i in range(0, len(values), len(keys)):
            result.append(dict(zip(keys, values[i : i + len(keys)])))  # noqa: E203
        return result
    else:
        LOGGER.debug("ValueError: Not enough values for the keys")


def get_names() -> List[Dict[str, str]]:
    """Get list of GPU model and vendor information based on the operating system."""
    fn_map = dict(linux=_linux, darwin=_darwin, windows=_windows)
    try:
        return fn_map[models.OPERATING_SYSTEM]()
    except (subprocess.SubprocessError, FileNotFoundError) as error:
        LOGGER.debug(error)
