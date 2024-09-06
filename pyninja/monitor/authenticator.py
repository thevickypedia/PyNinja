import secrets
import base64
import logging
import ast
from datetime import datetime
from typing import Dict, List, NoReturn, Union

from fastapi import HTTPException, Request, status

from pyninja import squire, models, monitor

LOGGER = logging.getLogger("uvicorn.default")

async def failed_auth_counter(request: Request) -> None:
    """Keeps track of failed login attempts from each host, and redirects if failed for 3 or more times.

    Args:
        request: Takes the ``Request`` object as an argument.
    """
    try:
        models.ws_session.invalid[request.client.host] += 1
    except KeyError:
        models.ws_session.invalid[request.client.host] = 1
    if models.ws_session.invalid[request.client.host] >= 3:
        raise monitor.config.RedirectException(location="/error")


async def raise_error(request) -> NoReturn:
    """Raises a 401 Unauthorized error in case of bad credentials."""
    await failed_auth_counter(request)
    LOGGER.error("Incorrect username or password: %d", models.ws_session.invalid[request.client.host])
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers=None
    )


async def extract_credentials(request: Request) -> List[str]:
    """Extract the credentials from ``Authorization`` headers and decode it before returning as a list of strings."""
    auth_header = request.headers.get("authorization", "")
    # decode the Base64-encoded ASCII string
    if not auth_header:
        await raise_error(request)
    decoded_auth = await monitor.secure.base64_decode(auth_header)
    # convert hex to a string
    auth = await monitor.secure.hex_decode(decoded_auth)
    return auth.split(',')


async def verify_login(request: Request) -> Dict[str, Union[str, int]]:
    """Verifies authentication and generates session token for each user.

    Returns:
        Dict[str, str]:
        Returns a dictionary with the payload required to create the session token.
    """
    username, signature, timestamp = await extract_credentials(request)
    if secrets.compare_digest(username, models.env.monitor_username):
        hex_user = await monitor.secure.hex_encode(models.env.monitor_username)
        hex_pass = await monitor.secure.hex_encode(models.env.monitor_password)
    else:
        LOGGER.warning("User '%s' not allowed", username)
        await raise_error(request)
    message = f"{hex_user}{hex_pass}{timestamp}"
    expected_signature = await monitor.secure.calculate_hash(message)
    if secrets.compare_digest(signature, expected_signature):
        models.ws_session.invalid[request.client.host] = 0
        key = squire.keygen()
        models.ws_session.client_auth[request.client.host] = dict(
            username=username, token=key, timestamp=int(timestamp)
        )
        return models.ws_session.client_auth[request.client.host]
    await raise_error(request)


async def generate_cookie(auth_payload: dict) -> Dict[str, str | bool | int]:
    """Generate a cookie for monitoring page.

    Args:
        auth_payload: Authentication payload containing username and timestamp.

    Returns:
        Dict[str, str | bool | int]:
        Returns a dictionary with cookie details
    """
    expiration = monitor.squire.get_expiry(lease_start=auth_payload['timestamp'],
                                           lease_duration=models.env.monitor_session)
    LOGGER.info("Session for '%s' will be valid until %s", auth_payload['username'], expiration)
    encoded_payload = str(auth_payload).encode("ascii")
    client_token = base64.b64encode(encoded_payload).decode("ascii")
    return dict(
        key="session_token",
        value=client_token,
        samesite="strict",
        path="/",
        httponly=False,  # Set to False explicitly, for WebSocket
        expires=expiration,
    )


async def validate_session(host: str, cookie_string: str) -> bool:
    """Validate the session token.

    Args:
        host: Hostname from the request.
        cookie_string: Session token from the cookie.

    Returns:
        bool:
        Returns True if the session token is valid.
    """
    if not cookie_string:
        LOGGER.warning("No session token found for %s", host)
        return False
    try:
        decoded_payload = base64.b64decode(cookie_string)
        decoded_str = decoded_payload.decode("ascii")
        original_dict = ast.literal_eval(decoded_str)
        assert (
                models.ws_session.client_auth.get(host) == original_dict
        ), f"{original_dict} != {models.ws_session.client_auth.get(host)}"
        poached = datetime.fromtimestamp(
            original_dict.get("timestamp") + models.env.monitor_session
        )
        LOGGER.info(
            "Session token validated for %s until %s",
            host,
            poached.strftime("%Y-%m-%d %H:%M:%S"),
        )
        return True
    except (KeyError, ValueError, TypeError) as error:
        LOGGER.critical(error)
    except AssertionError as error:
        LOGGER.error("Session token mismatch: %s", error)
    return False
