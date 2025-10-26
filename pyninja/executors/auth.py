import logging
import secrets
import time
from datetime import datetime
from http import HTTPStatus

import pyotp
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import database
from pyninja.modules import enums, exceptions, models

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
        timestamp = database.get_forbidden(request.client.host)
        if timestamp and timestamp > EPOCH():
            LOGGER.warning(
                "%s is forbidden until %s due to repeated login failures",
                request.client.host,
                datetime.fromtimestamp(timestamp).strftime("%c"),
            )
            raise exceptions.APIResponse(
                status_code=HTTPStatus.FORBIDDEN.real,
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
            LOGGER.debug("User agent: %s", user_agent)
        return
    # Adds host address to the forbidden set
    await handle_auth_error(request)
    raise exceptions.APIResponse(status_code=HTTPStatus.UNAUTHORIZED.real, detail=HTTPStatus.UNAUTHORIZED.phrase)


def validate_otp(code: str) -> bool:
    """Validate MFA generated through authenticator.

    Args:
        code: OTP code generated from authenticator app.

    Returns:
        bool:
        Returns a boolean flag to indicate if the OTP code is valid.
    """
    totp = pyotp.TOTP(models.env.authenticator_token)
    return totp.verify(code)


def verify_mfa(mfa_code: str) -> bool:
    """Verifies the multifactor authentication code.

    Args:
        mfa_code: Multifactor authentication code to verify.

    Returns:
        bool:
        Returns a boolean flag to indicate if the MFA code is valid.
    """
    if not mfa_code:
        LOGGER.error("No MFA code provided.")
        return False
    if models.env.authenticator_token and validate_otp(code=mfa_code):
        LOGGER.info("MFA code validated successfully using authenticator app.")
        return True
    stored_mfa_token = database.get_token(table=enums.TableName.mfa_token)
    if stored_mfa_token and secrets.compare_digest(mfa_code, stored_mfa_token):
        LOGGER.info("MFA code validated successfully using stored token.")
        return True
    LOGGER.error("Invalid MFA code provided.")
    return False


async def level_2(
    request: Request,
    apikey: HTTPAuthorizationCredentials,
    api_secret: str,
    mfa_code: str,
) -> None:
    """Validates the auth request using HTTPBearer and additionally a secure token.

    Args:
        request: Takes the authorization header token as an argument.
        apikey: Basic APIKey required for all the routes.
        api_secret: API secret for secured endpoints.
        mfa_code: Multifactor authentication code for additional security.

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
    if api_secret and secrets.compare_digest(api_secret, models.env.api_secret):
        if verify_mfa(mfa_code):
            LOGGER.info("MFA verification successful for %s", request.client.host)
            return
    # Adds host address to the forbidden set
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
            database.remove_forbidden(request.client.host)
            database.put_forbidden(request.client.host, until)
        elif models.session.auth_counter[request.client.host] > 3:
            # Allows up to 3 failed login attempts
            models.session.forbid.add(request.client.host)
            minutes = await incrementer(models.session.auth_counter[request.client.host])
            until = EPOCH() + minutes * 60
            LOGGER.warning(
                "%s is blocked (for %d minutes) until %s",
                request.client.host,
                minutes,
                datetime.fromtimestamp(until).strftime("%c"),
            )
            database.remove_forbidden(request.client.host)
            database.put_forbidden(request.client.host, until)
    else:
        LOGGER.warning("Failed auth, attempt #1 for %s", request.client.host)
        models.session.auth_counter[request.client.host] = 1
