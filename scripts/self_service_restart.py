import os
import sys
import time
from typing import Any, Dict, List

import requests
from fileio import run_command
from init import NINJA_API_URL, SERVER_PASSWORD
from runbook_coverage import Colors, Format

NEW_VERSION = os.environ["UPDATE_VERSION"]
PYTHON_PATH = os.environ.get("SERVER_PYTHON_PATH", "~/pyninja/venv/bin/python")
USE_STREAMING = os.environ.get("USE_STREAMING", "true").lower() == "true"
PROCESS_NAME = os.getenv("PROCESS_NAME")


def check_pypi_version() -> str:
    """Checks if the new version exists on PyPI."""
    response = requests.get("https://pypi.org/pypi/pyninja/json")
    for release in response.json()["releases"].keys():
        if release == NEW_VERSION:
            green(f"Version {NEW_VERSION} found on PyPI.")
            return release
    red(f"Version {NEW_VERSION} not found on PyPI.", bold=True)
    exit(1)


def terminal_size() -> int:
    """Returns the size of the terminal in columns."""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


TERM_SIZE = terminal_size()
INTERACTIVE = sys.stdin.isatty()


def self_restart() -> None:
    """Restarts the PyNinja service based on the operating system."""
    output = run_command('python -c "import platform; print(platform.system())"')
    if output["stdout"] == ["Darwin"]:
        return print_output(
            run_command(
                f"launchctl kickstart -k gui/$(id -u)/{PROCESS_NAME or 'pyninja-process'}",
                timeout=300,
            )
        )
    elif output["stdout"] == ["Linux"]:
        assert SERVER_PASSWORD, "SERVER_PASSWORD is not set in the environment."
        return print_output(
            run_command(
                f"echo {SERVER_PASSWORD} | sudo -S systemctl restart {PROCESS_NAME or 'pyninja.service'}",
                timeout=300,
            )
        )


def red(msg: str, bold: bool = False) -> None:
    """Prints a message in red color."""
    print("\n" + "*" * TERM_SIZE)
    if bold:
        print(f"{Colors.RED}{Format.BOLD}{msg}{Format.END}")
    else:
        print(f"{Colors.RED}{msg}{Format.END}")


def green(msg: str, bold: bool = False, light: bool = False) -> None:
    """Prints a message in green color."""
    print("\n" + "*" * TERM_SIZE)
    color = Colors.LIGHT_GREEN if light else Colors.GREEN
    if bold:
        print(f"{color}{Format.BOLD}{msg}{Format.END}")
    else:
        print(f"{color}{msg}{Format.END}")


def yellow(msg: str, bold: bool = False, light: bool = False) -> None:
    """Prints a message in green color."""
    print("\n" + "*" * TERM_SIZE)
    color = Colors.LIGHT_YELLOW if light else Colors.YELLOW
    if bold:
        print(f"{color}{Format.BOLD}{msg}{Format.END}")
    else:
        print(f"{color}{msg}{Format.END}")


def print_output(output: Dict[str, List[str]]) -> None:
    """Prints the output of a command execution."""
    stdout = output["stdout"]
    stderr = output["stderr"]
    if stderr and "[sudo] password" not in stderr[0]:
        red(f"Error: {output['stderr']}")
        exit(1)
    for line in stdout:
        print(line)


def write_screen(text: Any) -> None:
    """Write text on screen that can be cleared later.

    Args:
        text: Text to be written.
    """
    text = str(text).strip()
    if INTERACTIVE:
        sys.stdout.write(f"\r{' ' * TERM_SIZE}")
        if len(text) > TERM_SIZE:
            # Get 90% of the text size and ONLY print that on screen
            size = round(TERM_SIZE * (90 / 100))
            sys.stdout.write(f"\r{text[:size].strip()}...")
            return
    sys.stdout.write(f"\r{text}")


def flush_screen() -> None:
    """Flushes the screen output.

    See Also:
        Writes new set of empty strings for the size of the terminal if ran using one.
    """
    if INTERACTIVE:
        sys.stdout.write(f"\r{' ' * TERM_SIZE}")
    else:
        sys.stdout.write("\r")


def sleep(seconds: int) -> None:
    """Sleeps for the specified number of seconds."""
    green(f"Sleeping for {seconds} seconds...")
    for i in range(seconds):
        write_screen(f"{seconds - i} seconds remaining")
        time.sleep(1)
    flush_screen()
    green("Woke up!")


def commands() -> Dict[str, str]:
    """Returns a dictionary of commands to be executed."""
    return [
        dict(
            command=f"{PYTHON_PATH} -m pip install --upgrade pip",
            timeout=30,
            post_delay=5,
        ),
        dict(
            command=f"{PYTHON_PATH} -m pip install --no-cache --no-cache-dir --force-reinstall PyNinja=={NEW_VERSION}",
            timeout=300,
            post_delay=10,
        ),
        dict(
            command=(
                f"{PYTHON_PATH} -m pip uninstall --no-cache --no-cache-dir PyNinja -y && "
                f"{PYTHON_PATH} -m pip install --no-cache --no-cache-dir --force-reinstall PyNinja=={NEW_VERSION}"
            ),
            timeout=300,
            post_delay=5,
        ),
        dict(
            command=f"{PYTHON_PATH} -m pip freeze | grep PyNinja",
            timeout=30,
            post_delay=3,
        ),
        dict(
            command=f"{PYTHON_PATH} -c 'import pyninja; print(pyninja.version.__version__)'",
            timeout=30,
            post_delay=0,
        ),
    ]


def self_upgrade() -> None:
    """Upgrades the PyNinja service to a new version."""
    check_pypi_version()
    green(f"Upgrading PyNinja service for {NINJA_API_URL} to version {NEW_VERSION}")
    upgrade_commands = commands()
    for cmd in upgrade_commands:
        green(f"Running command: {cmd['command']}")
        output = run_command(cmd["command"], timeout=cmd["timeout"], stream=USE_STREAMING)
        if USE_STREAMING:
            for line in output:
                print(line)
        else:
            print_output(output)
        sleep(cmd["post_delay"])
    green("Restarting the PyNinja service...")
    self_restart()
    green("After restart:")
    cmd = upgrade_commands[-1]
    print_output(run_command(cmd["command"], timeout=cmd["timeout"], stream=False))


if __name__ == "__main__":
    self_upgrade()
