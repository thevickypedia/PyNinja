import os
import string
import time

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


def capwords_filter(value: str) -> str:
    """Capitalizes a string.

    Args:
        value: String value to be capitalized.

    See Also:
        This function is added as a filter to Jinja2 templates.

    Returns:
        str:
        Returns the capitalized string.
    """
    if value.endswith("_raw"):
        parts = value.split("_")
        return " ".join(parts[:-1])
    if value.endswith("_cap"):
        parts = value.split("_")
        return parts[0].upper() + " " + " ".join(parts[1:-1])
    return string.capwords(value).replace("_", " ")


templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)
# Add custom filter to Jinja2 environment
templates.env.filters["capwords"] = capwords_filter


async def clear_session(response: HTMLResponse) -> HTMLResponse:
    """Clear the session token from the response.

    Args:
        response: Takes the ``Response`` object as an argument.

    Returns:
        Response:
        Returns the response object with the session token cleared.
    """
    response.delete_cookie("session_token")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Authorization"] = ""
    return response


async def get_expiry(lease_start: int, lease_duration: int) -> str:
    """Get expiry datetime as string using max age.

    Args:
        lease_start: Time when the authentication was made.
        lease_duration: Number of seconds until expiry.

    Returns:
        str:
        Returns the date and time of expiry in GMT.
    """
    end = time.gmtime(lease_start + lease_duration)
    return time.strftime("%a, %d-%b-%Y %T GMT", end)
