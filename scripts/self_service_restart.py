import os
import sys
import time
from typing import Any, Dict, List

import requests
from fileio import run_command
from init import NINJA_API_URL, SERVER_PASSWORD
from runbook_coverage import Colors, Format

NEW_VERSION = os.environ["UPDATE_VERSION"]
SERVER_PYTHON_PATH = os.environ.get("SERVER_PYTHON_PATH", "~/pyninja/venv/bin/python")


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
                "launchctl kickstart -k gui/$(id -u)/pyninja-process", timeout=300
            )
        )
    elif output["stdout"] == ["Linux"]:
        assert SERVER_PASSWORD, "SERVER_PASSWORD is not set in the environment."
        return print_output(
            run_command(
                f"echo {SERVER_PASSWORD} | sudo -S systemctl restart pyninja.service",
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


class Commands:
    """Commands used for self upgrade."""

    pip_upgrade = f"{SERVER_PYTHON_PATH} -m pip install --upgrade pip"
    force_reinstall = f"{SERVER_PYTHON_PATH} -m pip install --no-cache --no-cache-dir --force-reinstall PyNinja=={NEW_VERSION}"  # noqa: E501
    uninstall_and_reinstall = (
        f"{SERVER_PYTHON_PATH} -m pip uninstall --no-cache --no-cache-dir PyNinja -y && "
        f"{SERVER_PYTHON_PATH} -m pip install --no-cache --no-cache-dir --force-reinstall PyNinja=={NEW_VERSION}"
    )
    pip_freeze = f"{SERVER_PYTHON_PATH} -m pip freeze | grep PyNinja"
    dist_check = (
        f"{SERVER_PYTHON_PATH} -c 'import pyninja; print(pyninja.version.__version__)'"
    )


def self_upgrade() -> None:
    """Upgrades the PyNinja service to a new version."""
    check_pypi_version()
    green(f"Upgrading PyNinja service for {NINJA_API_URL} to version {NEW_VERSION}")

    remote_server_version = run_command(
        Commands.dist_check,
        timeout=30,
    )
    use_streaming = (
        float(".".join(remote_server_version.get("stdout", [""])[0].split(".")[:2]))
        >= 4.3
    )
    green(f"Before upgrade: {remote_server_version}")
    if use_streaming:
        green("Using streaming for command output.")
    else:
        yellow("Not using streaming for command output.")

    if use_streaming:
        for line in run_command(
            Commands.pip_upgrade,
            timeout=30,
            stream=use_streaming,
        ):
            print(line)
    else:
        print_output(
            run_command(
                Commands.pip_upgrade,
                timeout=30,
                stream=use_streaming,
            )
        )

    sleep(5)
    green(f"Force reinstalling {NEW_VERSION}")
    if use_streaming:
        for line in run_command(
            Commands.force_reinstall,
            timeout=300,
            stream=use_streaming,
        ):
            print(line)
    else:
        print_output(
            run_command(
                Commands.force_reinstall,
                timeout=300,
                stream=use_streaming,
            )
        )
    sleep(10)

    if use_streaming:
        for line in run_command(
            Commands.uninstall_and_reinstall,
            timeout=300,
            stream=use_streaming,
        ):
            print(line)
    else:
        print_output(
            run_command(
                Commands.uninstall_and_reinstall,
                timeout=300,
                stream=use_streaming,
            )
        )
    sleep(5)
    green("Pip freeze output:")
    print_output(run_command(Commands.pip_freeze, timeout=30, stream=use_streaming))
    sleep(3)
    self_restart()
    sleep(5)
    green("After upgrade:")
    print_output(
        run_command(
            Commands.dist_check,
            timeout=30,
            stream=use_streaming,
        )
    )


if __name__ == "__main__":
    self_upgrade()
