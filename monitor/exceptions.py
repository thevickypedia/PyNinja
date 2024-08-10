from fastapi.exceptions import HTTPException


class APIResponse(HTTPException):
    """Custom ``HTTPException`` from ``FastAPI`` to wrap an API response.

    >>> APIResponse

    """


class ServiceNotFound(LookupError):
    """Custom exception for service not found.

    >>> ServiceNotFound

    """


class UnSupportedOS(RuntimeError):
    """Custom exception class for unsupported OS.

    >>> UnSupportedOS

    """
