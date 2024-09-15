from typing import NoReturn, Optional

from fastapi.exceptions import HTTPException


class APIResponse(HTTPException):
    """Custom ``HTTPException`` from ``FastAPI`` to wrap an API response.

    >>> APIResponse

    """


class UnSupportedOS(RuntimeError):
    """Custom exception class for unsupported OS.

    >>> UnSupportedOS

    """


class RedirectException(Exception):
    """Custom ``RedirectException`` raised within the API since HTTPException doesn't support returning HTML content.

    >>> RedirectException

    See Also:
        - RedirectException allows the API to redirect on demand in cases where returning is not a solution.
        - There are alternatives to raise HTML content as an exception but none work with our use-case with JavaScript.
        - This way of exception handling comes handy for many unexpected scenarios.

    References:
        https://fastapi.tiangolo.com/tutorial/handling-errors/#install-custom-exception-handlers
    """

    def __init__(self, location: str, detail: Optional[str] = ""):
        """Instantiates the ``RedirectException`` object with the required parameters.

        Args:
            location: Location for redirect.
            detail: Reason for redirect.
        """
        self.location = location
        self.detail = detail


class SessionError(Exception):
    """Custom exception class for session errors.

    >>> SessionError

    """

    def __init__(self, detail: Optional[str] = ""):
        """Instantiates the ``SessionError`` object."""
        self.detail = detail


def raise_os_error(operating_system: str) -> NoReturn:
    """Raises a custom exception for unsupported OS.

    Args:
        operating_system: Current operating system.

    Raises:
        ValidationError: Overridden exception from ``pydantic.ValidationError`` for unsupported OS.
    """
    raise UnSupportedOS(
        f"{operating_system!r} is unsupported.\n\t"
        "Host machine should either be macOS, Windows or any Linux distros"
    )
