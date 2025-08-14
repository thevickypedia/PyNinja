import os
import sys
import time
from typing import Any, Dict, List

from fileio import run_command
from init import NINJA_API_URL, SERVER_PASSWORD
from runbook_coverage import Colors, Format

from pyninja.version import __version__

NEW_VERSION = os.environ.get("UPDATE_VERSION", __version__)
SERVER_PYTHON_PATH = os.environ.get("SERVER_PYTHON_PATH", "~/pyninja/venv/bin/python")


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


def self_upgrade() -> None:
    """Upgrades the PyNinja service to a new version."""
    green(f"Upgrading PyNinja service for {NINJA_API_URL} to version {NEW_VERSION}")
    print_output(
        run_command(
            f"{SERVER_PYTHON_PATH} -m pip install --upgrade pip",
            timeout=30,
        )
    )
    sleep(5)
    green("Before upgrade:")
    print_output(
        run_command(
            f"{SERVER_PYTHON_PATH} -c 'import pyninja; print(pyninja.version.__version__)'",
            timeout=30,
        )
    )
    sleep(10)
    green(f"Force reinstalling {NEW_VERSION}")
    print_output(
        run_command(
            f"{SERVER_PYTHON_PATH} -m pip install --no-cache --no-cache-dir --force-reinstall PyNinja=={NEW_VERSION}",
            timeout=300,
        )
    )
    sleep(30)
    print_output(
        run_command(
            f"{SERVER_PYTHON_PATH} -m pip uninstall --no-cache --no-cache-dir PyNinja -y && "
            f"{SERVER_PYTHON_PATH} -m pip install --no-cache --no-cache-dir --force-reinstall PyNinja=={NEW_VERSION}",
            timeout=300,
        )
    )
    sleep(10)
    green("Pip freeze output:")
    print_output(
        run_command(f"{SERVER_PYTHON_PATH} -m pip freeze | grep PyNinja", timeout=30)
    )
    sleep(3)
    self_restart()
    sleep(10)
    green("After upgrade:")
    print_output(
        run_command(
            f"{SERVER_PYTHON_PATH} -c 'import pyninja; print(pyninja.version.__version__)'",
            timeout=30,
        )
    )


if __name__ == "__main__":
    self_restart()
