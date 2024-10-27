import logging
import mimetypes
import os
import pathlib
import subprocess
from http import HTTPStatus
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBearer
from pydantic import DirectoryPath

from pyninja.executors import auth, squire
from pyninja.modules import exceptions, payloads, tree

LOGGER = logging.getLogger("uvicorn.default")
BASIC_AUTH = HTTPBasic()
BEARER_AUTH = HTTPBearer()

router = APIRouter()


async def run_command(
    request: Request,
    payload: payloads.RunCommand,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """**API function to run a command on host machine.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - payload: Payload received as request body.
        - apikey: API Key to authenticate the request.
        - token: API secret to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_2(request, apikey, token)
    LOGGER.info(
        "Requested command: '%s' with timeout: %ds", payload.command, payload.timeout
    )
    try:
        response = squire.process_command(payload.command, payload.timeout)
    except subprocess.TimeoutExpired as warn:
        LOGGER.warning(warn)
        raise exceptions.APIResponse(
            status_code=HTTPStatus.REQUEST_TIMEOUT, detail=warn.__str__()
        )
    return response


async def list_files(
    request: Request,
    payload: payloads.ListFiles,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """**Get all YAML files from fileio and all log files from logs directory.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - payload: Payload received as request body.
        - apikey: API Key to authenticate the request.
        - token: API secret to authenticate the request.

    **Returns:**

        Dict[str, List[str]]:
        Dictionary of files that can be downloaded or uploaded.
    """
    await auth.level_2(request, apikey, token)
    if payload.deep_scan:
        if not payload.include_directories:
            raise exceptions.APIResponse(
                status_code=HTTPStatus.BAD_REQUEST.real,
                detail="'include_directories' must be set to True for 'deep_scan'",
            )
        tree_scanner = tree.Tree(not payload.show_hidden_files)
        return tree_scanner.scan(path=pathlib.Path(payload.directory))
    if payload.include_directories and payload.show_hidden_files:
        return os.listdir(payload.directory)
    elif payload.include_directories:
        return [f for f in os.listdir(payload.directory) if not f.startswith(".")]
    elif payload.show_hidden_files:
        return [
            f
            for f in os.listdir(payload.directory)
            if os.path.isfile(os.path.join(payload.directory, f))
        ]
    else:
        return [
            f
            for f in os.listdir(payload.directory)
            if not f.startswith(".")
            and not os.path.isdir(os.path.join(payload.directory, f))
        ]


async def get_file(
    request: Request,
    payload: payloads.GetFile,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """**Download a particular YAML file from fileio or log file from logs directory.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - payload: Payload received as request body.
        - apikey: API Key to authenticate the request.
        - token: API secret to authenticate the request.

    **Returns:**

        FileResponse:
        Returns the FileResponse object of the file.
    """
    await auth.level_2(request, apikey, token)
    LOGGER.info("Requested file: '%s' for download.", payload.filepath)
    mimetype = mimetypes.guess_type(payload.filepath.name, strict=True)
    if mimetype:
        filetype = mimetype[0]
    else:
        filetype = "unknown"
    return FileResponse(
        status_code=HTTPStatus.OK.real,
        path=payload.filepath,
        media_type=filetype,
        filename=payload.filepath.name,
    )


async def put_file(
    request: Request,
    file: UploadFile,
    directory: DirectoryPath,
    overwrite: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """**Upload a file to th.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - file: Upload object for the file param.
        - payload: Payload received as request body.
        - apikey: API Key to authenticate the request.
        - token: API secret to authenticate the request.
    """
    await auth.level_2(request, apikey, token)
    LOGGER.info(
        "Requested file: '%s' for upload at %s",
        file.filename,
        directory,
    )
    content = await file.read()
    if not overwrite and os.path.isfile(os.path.join(directory, file.filename)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.BAD_REQUEST.real,
            detail=f"File {file.filename!r} exists at {str(directory)!r} already, "
            "set 'overwrite' flag to True to overwrite.",
        )
    with open(os.path.join(directory, file.filename), "wb") as f_stream:
        f_stream.write(content)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.OK.real,
        detail=f"{file.filename!r} was uploaded to {directory}.",
    )
