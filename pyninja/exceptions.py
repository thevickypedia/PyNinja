from fastapi.exceptions import HTTPException


# todo: move this out of "exceptions"
class APIResponse(HTTPException):
    """Custom ``HTTPException`` from ``FastAPI`` to wrap an API response.

    >>> APIResponse

    """


class UnSupportedOS(RuntimeError):
    """Custom exception class for unsupported OS.

    >>> UnSupportedOS

    """
