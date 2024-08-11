import logging
import secrets
import time
from datetime import datetime
from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.security import HTTPBasicCredentials, HTTPBearer

from pyninja import database, exceptions, models

LOGGER = logging.getLogger("uvicorn.error")
EPOCH = lambda: int(time.time())  # noqa: E731
SECURITY = HTTPBearer()


async def authenticator(token: HTTPBasicCredentials = Depends(SECURITY)) -> None:
    """Validates the token if mentioned as a dependency.

    Args:
        token: Takes the authorization header token as an argument.

    Raises:
        APIResponse:
        - 401: If authorization is invalid.
    """
    auth = token.model_dump().get("credentials", "")
    if auth.startswith("\\"):
        auth = bytes(auth, "utf-8").decode(encoding="unicode_escape")
    if secrets.compare_digest(auth, models.env.apikey):
        return
    raise exceptions.APIResponse(
        status_code=HTTPStatus.UNAUTHORIZED.real, detail=HTTPStatus.UNAUTHORIZED.phrase
    )


async def incrementer(attempt: int) -> int:
    """Increments block time for a host address based on the number of failed attempts.

    Args:
        attempt: Number of failed attempts.

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
