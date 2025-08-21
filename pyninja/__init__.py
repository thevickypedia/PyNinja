"""Placeholder for packaging."""

import sys

import click

from .main import start, version
from .multifactor import otp


@click.command()
@click.argument("start", required=False)
@click.option("--version", "-V", is_flag=True, help="Prints the version.")
@click.option("--help", "-H", is_flag=True, help="Prints the help section.")
@click.option("--mfa", is_flag=True, help="Generates a QR code for TOTP setup.")
@click.option(
    "--env",
    "-E",
    type=click.Path(exists=True),
    help="Environment configuration filepath.",
)
def commandline(*args, **kwargs) -> None:
    """Starter function to invoke PyNinja via CLI commands.

    **Flags**
        - ``--version | -V``: Prints the version.
        - ``--help | -H``: Prints the help section.
        - ``--mfa``: Generates a QR code for TOTP setup.
        - ``--env | -E``: Environment configuration filepath.

    **Commands**
        ``start``: Initiates PyNinja API server.
    """
    assert sys.argv[0].lower().endswith("pyninja"), "Invalid commandline trigger!!"
    options = {
        "--version | -V": "Prints the version.",
        "--help | -H": "Prints the help section.",
        "--env | -E": "Environment configuration filepath.",
        "--mfa": "Generates a QR code for TOTP setup.",
        "start": "Initiates PyNinja API server.",
    }
    # weird way to increase spacing to keep all values monotonic
    _longest_key = len(max(options.keys()))
    _pretext = "\n\t* "
    choices = _pretext + _pretext.join(
        f"{k} {'·' * (_longest_key - len(k) + 8)}→ {v}".expandtabs() for k, v in options.items()
    )
    if kwargs.get("version"):
        click.echo(f"PyNinja {version.__version__}")
        sys.exit(0)
    if kwargs.get("help"):
        click.echo(f"\nUsage: pyninja [arbitrary-command]\nOptions (and corresponding behavior):{choices}")
        sys.exit(0)
    if kwargs.get("mfa"):
        otp.generate_qr(show_qr=True)
        sys.exit(0)
    if kwargs.get("start") == "start":
        # Click doesn't support assigning defaults like traditional dictionaries, so kwargs.get("max", 100) won't work
        start(env_file=kwargs.get("env"))
        sys.exit(0)
    else:
        click.secho("\nNo command provided", fg="red")
    click.echo(f"Usage: pyninja [arbitrary-command]\nOptions (and corresponding behavior):{choices}")
    sys.exit(1)
