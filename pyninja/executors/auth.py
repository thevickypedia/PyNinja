import logging
import secrets
import time
from datetime import datetime
from http import HTTPStatus

from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import database
from pyninja.modules import exceptions, models

LOGGER = logging.getLogger("uvicorn.default")
EPOCH = lambda: int(time.time())  # noqa: E731
SECURITY = HTTPBearer()


async def forbidden(request: Request) -> None:
    """Validates if a request is part of the forbidden list.

    Args:
        request: Reference to the FastAPI request object.

    Raises:
        APIResponse:
        - 403: If host address is forbidden.
    """
    # placeholder list, to avoid a DB search for every request
    if request.client.host in models.session.forbid:
        # Get timestamp until which the host has to be forbidden
        timestamp = database.get_record(request.client.host)
        if timestamp and timestamp > EPOCH():
            LOGGER.warning(
                "%s is forbidden until %s due to repeated login failures",
                request.client.host,
                datetime.fromtimestamp(timestamp).strftime("%c"),
            )
            raise exceptions.APIResponse(
                status_code=HTTPStatus.FORBIDDEN.value,
                detail=f"{request.client.host!r} is not allowed",
            )


async def level_1(request: Request, apikey: HTTPAuthorizationCredentials) -> None:
    """Validates the auth request using HTTPBearer.

    Args:
        request: Takes the authorization header token as an argument.
        apikey: Basic APIKey required for all the routes.

    Raises:
        APIResponse:
        - 401: If authorization is invalid.
        - 403: If host address is forbidden.
    """
    await forbidden(request)
    if apikey.credentials.startswith("\\"):
        auth = bytes(apikey.credentials, "utf-8").decode(encoding="unicode_escape")
    else:
        auth = apikey.credentials
    if secrets.compare_digest(auth, models.env.apikey):
        LOGGER.info(
            "Connection received from client-host: %s, host-header: %s, x-fwd-host: %s",
            request.client.host,
            request.headers.get("host"),
            request.headers.get("x-forwarded-host"),
        )
        if user_agent := request.headers.get("user-agent"):
            LOGGER.info("User agent: %s", user_agent)
        return
    # Adds host address to the forbidden set
    await handle_auth_error(request)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.UNAUTHORIZED.real, detail=HTTPStatus.UNAUTHORIZED.phrase
    )


async def level_2(
    request: Request, apikey: HTTPAuthorizationCredentials, token: str
) -> None:
    """Validates the auth request using HTTPBearer and additionally a secure token.

    Args:
        request: Takes the authorization header token as an argument.
        apikey: Basic APIKey required for all the routes.
        token: Additional token for critical requests.

    Raises:
        APIResponse:
        - 401: If authorization is invalid.
        - 403: If host address is forbidden.
    """
    await level_1(request, apikey)
    if not all((models.env.remote_execution, models.env.api_secret)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.NOT_IMPLEMENTED.real,
            detail="Remote execution has been disabled on the server.",
        )
    if token and secrets.compare_digest(token, models.env.api_secret):
        return
    await handle_auth_error(request)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.UNAUTHORIZED.real,
        detail=HTTPStatus.UNAUTHORIZED.phrase,
    )


async def incrementer(attempt: int) -> int:
    """Increments block time for a host address based on the number of failed login attempts.

    Args:
        attempt: Number of failed login attempts.

    Returns:
        int:
        Returns the appropriate block time in minutes.
    """
    try:
        return {4: 5, 5: 10, 6: 20, 7: 40, 8: 80, 9: 160, 10: 220}[attempt]
    except KeyError:
        LOGGER.critical("Something went horribly wrong for %dth attempt", attempt)
        return 60  # defaults to 1 hour


async def handle_auth_error(request: Request) -> None:
    """Handle authentication errors from the filebrowser API.

    Args:
        request: The incoming request object.
    """
    if models.session.auth_counter.get(request.client.host):
        models.session.auth_counter[request.client.host] += 1
        LOGGER.warning(
            "Failed auth, attempt #%d for %s",
            models.session.auth_counter[request.client.host],
            request.client.host,
        )
        if models.session.auth_counter[request.client.host] >= 10:
            # Block the host address for 1 month or until the server restarts
            until = EPOCH() + 2_592_000
            LOGGER.warning(
                "%s is blocked until %s",
                request.client.host,
                datetime.fromtimestamp(until).strftime("%c"),
            )
            database.remove_record(request.client.host)
            database.put_record(request.client.host, until)
        elif models.session.auth_counter[request.client.host] > 3:
            # Allows up to 3 failed login attempts
            models.session.forbid.add(request.client.host)
            minutes = await incrementer(
                models.session.auth_counter[request.client.host]
            )
            until = EPOCH() + minutes * 60
            LOGGER.warning(
                "%s is blocked (for %d minutes) until %s",
                request.client.host,
                minutes,
                datetime.fromtimestamp(until).strftime("%c"),
            )
            database.remove_record(request.client.host)
            database.put_record(request.client.host, until)
    else:
        LOGGER.warning("Failed auth, attempt #1 for %s", request.client.host)
        models.session.auth_counter[request.client.host] = 1
