from typing import Any, NoReturn, Optional, Tuple

from fastapi.exceptions import HTTPException
from pydantic import ValidationError
from pydantic_core import InitErrorDetails


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


def raise_os_error(error: Any, supported: Tuple[str, str, str]) -> NoReturn:
    """Raises a custom exception for unsupported OS.

    Raises:
        ValidationError: Overridden exception from ``pydantic.ValidationError`` for unsupported OS.
    """
    # https://docs.pydantic.dev/latest/errors/validation_errors/#model_type
    raise ValidationError.from_exception_data(
        title="PyNinja",
        line_errors=[
            InitErrorDetails(
                type="value_error",
                loc=("operating_system",),
                input="invalid",
                ctx={
                    "error": f"{error} is not a supported operating system.\n\tShould be one of {supported}"
                },
            )
        ],
    )
