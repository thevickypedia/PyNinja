"""This module provides functionality for generating a QR code for TOTP (Time-based One-Time Password) setup.

.. note::

    To generate a QR code, run one of the following:

    **Option 1: Python snippet**

    .. code-block:: python

        import pyninja
        pyninja.otp.generate_qr(show_qr=True)

    **Option 2: CLI command**

    .. code-block:: bash

        pyninja --mfa
"""

import os
import warnings

import pyotp
import qrcode

from pyninja.executors import squire
from pyninja.modules import models


def display_secret(secret: str, qr_filename: str) -> None:
    """Displays the TOTP secret key.

    Args:
        secret: The TOTP secret key to display.
        qr_filename: The filename where the QR code is saved.
    """
    try:
        term_size = os.get_terminal_size().columns
    except OSError:
        term_size = 120
    base = "*" * term_size
    print(
        f"\n{base}\n"
        f"\nYour TOTP secret key is: {secret}"
        f"\nStore this key as the environment variable `authenticator_token` in your .env file.\n"
        f"\nQR code saved as {qr_filename!r} (you can scan this with your Authenticator app).\n"
        f"\n{base}",
    )


def generate_qr(show_qr: bool = True) -> None:
    """Generates a QR code for TOTP setup.

    Args:
        - show_qr: If True, displays the QR code using the default image viewer.
    """
    models.env = squire.load_env()
    if models.env.authenticator_token:
        warnings.warn(
            "\n\nAuthenticator token already set — skipping OTP setup. "
            "To create a new one, remove the 'authenticator_token' environment variable.\n",
            UserWarning,
        )
        return

    # STEP 1: Generate a new secret key for the user (store this securely!)
    secret = pyotp.random_base32()

    # STEP 2: Create a provisioning URI (for the QR code)
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=str(models.env.authenticator_user), issuer_name=models.env.authenticator_app
    )

    # STEP 3: Generate a QR code (scan this with your authenticator app)
    qr = qrcode.make(uri)
    if show_qr:
        qr.show()

    # Save the QR code
    qr.save("totp_qr.png")
    display_secret(secret, "totp_qr.png")
