import logging
import os
import subprocess
from http import HTTPStatus
from typing import Optional

from fastapi import Depends, Header, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates

from pyninja.executors import auth, database, squire
from pyninja.modules import enums, exceptions, models, payloads

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()
TEMPLATES = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__)))


async def get_run_token(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    api_secret: Optional[str] = Header(None),
    mfa_code: Optional[str] = Header(None),
) -> str:
    """**Get the run token for remote execution.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - apikey: API Key to authenticate the request.
        - api_secret: API secret to authenticate the request.
        - mfa_code: Multifactor authentication code.

    **Returns:**
        str: Returns the run token for remote execution.

    **Raises:**
        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_2(request, apikey, api_secret, mfa_code)
    token = squire.keygen(256)
    database.update_token(
        token=token, table=enums.TableName.run_token, expiry=models.env.run_token_expiry
    )
    return token


async def run_ui(request: Request):
    """Renders the HTML template for the run command UI."""
    return TEMPLATES.TemplateResponse(
        name="run_ui.html",
        context={
            "request": request,
            "API_ENDPOINT": enums.APIEndpoints.run_command,
        },
    )


async def run_command(
    request: Request,
    payload: payloads.RunCommand,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    api_secret: Optional[str] = Header(None),
    mfa_code: Optional[str] = Header(None),
    run_token: Optional[str] = Header(None),
):
    """**API function to run a command on host machine.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - payload: Payload received as request body.
        - apikey: API Key to authenticate the request.
        - api_secret: API secret to authenticate the request.
        - mfa_code: Multifactor authentication code.
        - run_token: Single use run-token generated for each session.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_2(request, apikey, api_secret, mfa_code)
    await auth.verify_run_token(run_token)
    LOGGER.info(
        "Requested command: '%s' with timeout: %ds", payload.command, payload.timeout
    )
    if payload.stream:
        LOGGER.info("Streaming command output for: '%s'", payload.command)
        return StreamingResponse(
            squire.stream_command(payload.command, payload.timeout),
            media_type="text/plain",
        )
    else:
        try:
            return squire.process_command(payload.command, payload.timeout)
        except subprocess.CalledProcessError as error:
            squire.log_subprocess_error(error)
            raise exceptions.APIResponse(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR.real,
                detail=f"Command execution failed: {error.__str__()}",
            )
        except subprocess.TimeoutExpired as warn:
            LOGGER.warning(warn)
            raise exceptions.APIResponse(
                status_code=HTTPStatus.REQUEST_TIMEOUT.real, detail=warn.__str__()
            )
