import logging
import subprocess
from http import HTTPStatus
from typing import Optional

from fastapi import Depends, Header, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth, squire
from pyninja.modules import enums, exceptions, models, payloads

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def run_ui(request: Request):
    """Renders the HTML template for the run command UI."""
    return models.API_TEMPLATES.TemplateResponse(
        name=enums.Templates.run_ui.value,
        context={
            "request": request,
            "RUN_COMMAND_ENDPOINT": enums.APIEndpoints.run_command,
            "FILE_UPLOAD_ENDPOINT": enums.APIEndpoints.put_file,
            "FILE_DOWNLOAD_ENDPOINT": enums.APIEndpoints.get_file,
        },
    )


async def run_command(
    request: Request,
    payload: payloads.RunCommand,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    api_secret: Optional[str] = Header(None),
    mfa_code: Optional[str] = Header(None),
):
    """**API function to run a command on host machine.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - payload: Payload received as request body.
        - apikey: API Key to authenticate the request.
        - api_secret: API secret to authenticate the request.
        - mfa_code: Multifactor authentication code.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_2(request, apikey, api_secret, mfa_code)
    LOGGER.info("Requested command: '%s' with timeout: %ds, shell: %s", payload.command, payload.timeout, payload.shell)
    if payload.stream:
        if payload.stream_timeout > models.env.mfa_timeout:
            raise exceptions.APIResponse(
                status_code=HTTPStatus.BAD_REQUEST.real,
                detail=f"Stream timeout cannot be greater than MFA timeout of {models.env.mfa_timeout} seconds.",
            )
        LOGGER.info("Streaming command output for: '%s'", payload.command)
        return StreamingResponse(
            squire.stream_command(request, payload.command, payload.shell, payload.timeout, payload.stream_timeout),
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
            raise exceptions.APIResponse(status_code=HTTPStatus.REQUEST_TIMEOUT.real, detail=warn.__str__())
