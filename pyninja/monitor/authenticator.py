import ast
import base64
import logging
import secrets
from datetime import datetime
from typing import Dict, List, NoReturn, Union

from fastapi import Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials

from pyninja import version
from pyninja.executors import squire
from pyninja.modules import enums, exceptions, models, secure
from pyninja.monitor import config

LOGGER = logging.getLogger("uvicorn.default")


async def failed_auth_counter(host) -> None:
    """Keeps track of failed login attempts from each host, and redirects if failed for 3 or more times.

    Args:
        host: Host header from the request.
    """
    try:
        models.ws_session.invalid[host] += 1
    except KeyError:
        models.ws_session.invalid[host] = 1
    if models.ws_session.invalid[host] >= 3:
        raise exceptions.RedirectException(location="/error")


async def raise_error(host: str) -> NoReturn:
    """Raises a 401 Unauthorized error in case of bad credentials.

    Args:
        host: Host header from the request.
    """
    await failed_auth_counter(host)
    LOGGER.error(
        "Incorrect username or password: %d",
        models.ws_session.invalid[host],
    )
    raise exceptions.APIResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers=None,
    )


async def extract_credentials(
    authorization: HTTPAuthorizationCredentials, host: str
) -> List[str]:
    """Extract the credentials from ``Authorization`` headers and decode it before returning as a list of strings.

    Args:
        authorization: Authorization header from the request.
        host: Host header from the request.
    """
    if not authorization:
        await raise_error(host)
    decoded_auth = await secure.base64_decode(authorization.credentials)
    # convert hex to a string
    auth = await secure.hex_decode(decoded_auth)
    return auth.split(",")


async def verify_login(
    authorization: HTTPAuthorizationCredentials, host: str
) -> Dict[str, Union[str, int]]:
    """Verifies authentication and generates session token for each user.

    Returns:
        Dict[str, str]:
        Returns a dictionary with the payload required to create the session token.
    """
    username, signature, timestamp = await extract_credentials(authorization, host)
    if secrets.compare_digest(username, models.env.monitor_username):
        hex_user = await secure.hex_encode(models.env.monitor_username)
        hex_pass = await secure.hex_encode(models.env.monitor_password)
    else:
        LOGGER.warning("User '%s' not allowed", username)
        await raise_error(host)
    message = f"{hex_user}{hex_pass}{timestamp}"
    expected_signature = await secure.calculate_hash(message)
    if secrets.compare_digest(signature, expected_signature):
        models.ws_session.invalid[host] = 0
        key = squire.keygen()
        models.ws_session.client_auth[host] = dict(
            username=username, token=key, timestamp=int(timestamp)
        )
        return models.ws_session.client_auth[host]
    await raise_error(host)


async def generate_cookie(auth_payload: dict) -> Dict[str, str | bool | int]:
    """Generate a cookie for monitoring page.

    Args:
        auth_payload: Authentication payload containing username and timestamp.

    Returns:
        Dict[str, str | bool | int]:
        Returns a dictionary with cookie details
    """
    expiration = await config.get_expiry(
        lease_start=auth_payload["timestamp"], lease_duration=models.env.monitor_session
    )
    LOGGER.info(
        "Session for '%s' will be valid until %s", auth_payload["username"], expiration
    )
    encoded_payload = str(auth_payload).encode("ascii")
    client_token = base64.b64encode(encoded_payload).decode("ascii")
    return dict(
        key=enums.Cookies.session_token.value,
        value=client_token,
        samesite="strict",
        path="/",
        httponly=False,  # Set to False explicitly, for WebSocket
        expires=expiration,
    )


async def session_error(
    request: Request, error: exceptions.SessionError
) -> HTMLResponse:
    """Renders the session error page.

    Args:
        request: Reference to the FastAPI request object.
        error: Session error message.

    Returns:
        HTMLResponse:
        Returns an HTML response templated using Jinja2.
    """
    return config.templates.TemplateResponse(
        name=enums.Templates.session.value,
        context={
            "request": request,
            "signin": "/login",
            "reason": error.detail,
            "version": f"v{version.__version__}",
        },
    )


async def validate_session(host: str, cookie_string: str, log: bool = True) -> None:
    """Validate the session token.

    Args:
        host: Hostname from the request.
        cookie_string: Session token from the cookie.
        log: Boolean flag to enable logging.

    Raises:
        SessionError:
        Raises a SessionError with summary.
    """
    if models.env.no_auth:
        if log:
            LOGGER.info("No auth set! Bypassing auth filters!")
        return
    try:
        decoded_payload = base64.b64decode(cookie_string)
        decoded_str = decoded_payload.decode("ascii")
        original_dict = ast.literal_eval(decoded_str)
        assert (
            models.ws_session.client_auth.get(host) == original_dict
        ), f"{original_dict} != {models.ws_session.client_auth.get(host)}"
        if log:
            poached = datetime.fromtimestamp(
                original_dict.get("timestamp") + models.env.monitor_session
            )
            LOGGER.info(
                "Session token validated for %s until %s",
                host,
                poached.strftime("%Y-%m-%d %H:%M:%S"),
            )
    except (KeyError, ValueError, TypeError) as error:
        LOGGER.critical(error)
        raise exceptions.SessionError("Invalid Session")
    except AssertionError as error:
        LOGGER.debug(error)
        raise exceptions.SessionError("Session Expired")
