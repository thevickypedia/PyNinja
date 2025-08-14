# noinspection PyUnresolvedReferences
"""Special module for managing GUI applications on macOS.

>>> macOS - Applications

"""

import logging
import os
import subprocess
import time
from collections.abc import Generator
from http import HTTPStatus
from typing import Dict

import psutil
from pydantic import FilePath

from pyninja.executors import squire
from pyninja.modules import models

LOGGER = logging.getLogger("uvicorn.default")


def get_all_apps() -> Generator[Dict[str, str]]:
    """Get all GUI applications installed in the /Applications directory.

    Yields:
        Dict[str, str]:
        Yields a dictionary with the display name as the key and the application path as the value.
    """
    for entry in os.listdir("/Applications"):
        if entry.endswith(".app"):
            app_path = f"/Applications/{entry}"
            try:
                # Run `mdls` to get the display name
                result = subprocess.check_output(
                    [models.env.mdls, "-name", "kMDItemDisplayName", "-raw", app_path],
                    shell=True,
                    stderr=subprocess.DEVNULL,
                )
                if display_name := result.decode("utf-8").strip():
                    yield {display_name: app_path}
            except subprocess.CalledProcessError as error:
                squire.log_subprocess_error(error)
                # Ignore apps that fail mdls
                yield {entry.rstrip(".app"): app_path}


def is_app_running(app_name: str) -> bool:
    """Check if a GUI application is currently running.

    Args:
        app_name: Name of the application to check.

    Returns:
        bool:
        Returns True if the application is running, otherwise False.
    """
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] == app_name:
            return True
    return False


def unavailable(app_name: str) -> models.AppStatus:
    """Return an AppStatus indicating the application is unavailable.

    Args:
        app_name: Name of the application.

    Returns:
        AppStatus:
        Returns an instance of the AppStatus object with status code 404.
    """
    return models.AppStatus(
        app_name=app_name,
        status_code=HTTPStatus.NOT_FOUND.real,
        description=f"{app_name} is not available\nAvailable applications: {list(get_all_apps())}",
    )


def failed(app_name: str, app_path: FilePath, error: str) -> models.AppStatus:
    """Return an AppStatus indicating the application failed to restart.

    Args:
        app_name: Name of the application.
        app_path: Application path.
        error: Error message describing the failure.

    Returns:
        AppStatus:
        Returns an instance of the AppStatus object with status code 500.
    """
    return models.AppStatus(
        app_name=app_name,
        app_path=app_path,
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR.real,
        description=f"Failed to restart {app_name}: {error}",
    )


def success(app_name: str, app_path: str) -> models.AppStatus:
    """Return an AppStatus indicating the application restarted successfully.

    Args:
        app_name: Name of the application.
        app_path: Application path.

    Returns:
        AppStatus:
        Returns an instance of the AppStatus object with status code 200.
    """
    return models.AppStatus(
        app_name=app_name,
        app_path=app_path,
        status_code=HTTPStatus.OK.real,
        description=f"{app_name} restarted successfully",
    )


def stop_app(app_path: str) -> None:
    """Stop a GUI service by name.

    Args:
        app_path: Path to the application.
    """
    subprocess.check_output(
        [models.env.osascript, "-e", f'quit app "{app_path}"'],
        text=True,
    )


def start_app(app_path: str) -> None:
    """Start a GUI service by path.

    Args:
        app_path: Application path to start.
    """
    subprocess.check_output(
        [models.env.open, "-a", app_path],
        text=True,
    )


def get_app_by_name(app_name: str) -> Dict[str, str]:
    """Get the application path by its name.

    Args:
        app_name: Name of the application.

    Returns:
        Dict[str, str]:
        Returns a dictionary with the application name as the key and its path as the value.
    """
    app_name_lower = app_name.lower()
    for iterator in get_all_apps():
        for name, path in iterator.items():
            if app_name_lower == name.lower():
                return {"name": name, "path": path}
    return {}


def restart(app_name: str) -> models.AppStatus:
    """Restart a GUI service by name.

    Args:
        app_name: Name of the application.

    Returns:
        str | None:
        Returns the path to the application if restarted successfully, otherwise None.
    """
    if not (app_info := get_app_by_name(app_name)):
        LOGGER.error("Application %s not found", app_name)
        return unavailable(app_name)
    app_path = app_info["path"]
    try:
        stop_app(app_path)
        n = 0
        while is_app_running(app_name):
            if n > 10:
                LOGGER.error("Failed to quit %s after 10 attempts", app_name)
                return failed(app_name, app_path, f"Failed to quit {app_name}")
            LOGGER.debug("Still running at %d attempt, waiting to quit", n)
            n += 1
            time.sleep(0.5)
        start_app(app_path)
        return success(app_name, app_path)
    except subprocess.CalledProcessError as error:
        squire.log_subprocess_error(error)
        return failed(app_name, app_path, str(error))
