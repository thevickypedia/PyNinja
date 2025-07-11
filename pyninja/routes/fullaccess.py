import logging
import mimetypes
import os
import pathlib
import shutil
import subprocess
from http import HTTPStatus
from typing import NoReturn, Optional

from fastapi import Depends, Header, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import DirectoryPath, NewPath

from pyninja.executors import auth, squire
from pyninja.modules import exceptions, payloads, tree

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


def create_directory(directory: DirectoryPath | NewPath) -> None | NoReturn:
    """Create a directory if it does not exist.

    Args:
        directory: Directory path to create.

    Raises:
        APIResponse:
        Raises an INTERNAL_SERVER_ERROR if the directory cannot be created.
    """
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as err:
        LOGGER.error("Error creating directory: %s", err)
        raise exceptions.APIResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR.real,
            detail=f"Error creating directory {directory.__str__()!r}: {err}",
        )


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


async def delete_content(
    request: Request,
    payload: payloads.DeleteContent,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """**List files in a directory or scan the directory tree.**

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
    if not any((payload.filepath, payload.directory)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.BAD_REQUEST.real,
            detail="Either 'filepath' or 'directory' must be provided.",
        )
    if all((payload.filepath, payload.directory)):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.BAD_REQUEST.real,
            detail="Only one of 'filepath' or 'directory' can be provided.",
        )
    LOGGER.info("Requested file: '%s' for deletion.", payload.filepath)

    if payload.filepath:
        if not os.path.isfile(payload.filepath):
            raise exceptions.APIResponse(
                status_code=HTTPStatus.NOT_FOUND.real,
                detail=f"File {payload.filepath!r} does not exist.",
            )
        try:
            os.remove(payload.filepath)
        except OSError as err:
            LOGGER.error("Error deleting file: %s", err)
            raise exceptions.APIResponse(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR.real,
                detail=f"Error deleting file {payload.filepath.__str__()!r}: {err}",
            )
        LOGGER.info("File %s deleted successfully.", payload.filepath.__str__())
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real,
            detail=f"File {payload.filepath.__str__()!r} deleted successfully.",
        )

    if payload.directory:
        if not os.path.isdir(payload.directory):
            raise exceptions.APIResponse(
                status_code=HTTPStatus.NOT_FOUND.real,
                detail=f"Directory {payload.directory.__str__()!r} does not exist.",
            )
        try:
            if payload.recursive:
                shutil.rmtree(payload.directory)
            else:
                # Only delete the directory if it's empty
                os.rmdir(payload.directory)
        except OSError as err:
            LOGGER.error("Error deleting directory: %s", err)
            raise exceptions.APIResponse(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR.real,
                detail=f"Error deleting directory {payload.directory.__str__()!r}: {err}",
            )
        LOGGER.info("Directory %s deleted successfully.", payload.directory)
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real,
            detail=f"Directory {payload.directory.__str__()!r} deleted successfully.",
        )


async def list_files(
    request: Request,
    payload: payloads.ListFiles,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """**List files in a directory or scan the directory tree.**

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
    """**Download a particular file.**

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
    directory: DirectoryPath | NewPath,
    overwrite: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """**Upload a file to th.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - file: Upload object for the file param.
        - directory: Target directory for upload.
        - overwrite: Boolean flag to remove existing file.
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
    filepath = os.path.join(directory, file.filename)
    if not overwrite and os.path.isfile(filepath):
        raise exceptions.APIResponse(
            status_code=HTTPStatus.BAD_REQUEST.real,
            detail=f"File {file.filename!r} exists at {str(directory)!r} already, "
            "set 'overwrite' flag to True to overwrite.",
        )
    create_directory(directory)
    content = await file.read()
    with open(filepath, "wb") as f_stream:
        f_stream.write(content)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.OK.real,
        detail=f"{file.filename!r} was uploaded to {directory}.",
    )
