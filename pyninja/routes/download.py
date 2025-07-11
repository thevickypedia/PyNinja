"""Module to handle large file downloads in chunks via FastAPI with optional server-side compression."""

import logging
import mimetypes
import pathlib
import tempfile
from collections.abc import Generator
from http import HTTPStatus
from typing import Optional

from fastapi import Depends, Header, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import DirectoryPath, FilePath

from pyninja.executors import auth
from pyninja.features import zipper
from pyninja.modules import exceptions

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


def iter_file_chunks(filepath: pathlib.Path, chunk_size: int) -> Generator[bytes]:
    """Generator to read a file in chunks.

    Args:
        filepath: FilePath to read.
        chunk_size: Chunk size to read the file in bytes. Default is 8 KB.

    Yields:
        bytes:
        Yields chunks of the file as bytes.
    """
    with open(filepath, "rb") as file:
        while chunk := file.read(chunk_size):
            yield chunk


async def get_large_file(
    request: Request,
    filepath: Optional[FilePath] = None,
    directory: Optional[DirectoryPath] = None,
    chunk_size: int = 8192,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """API handler to download a large file or directory as a compressed archive.

    Args:
        - request: Reference to the FastAPI request object.
        - filepath: FilePath to the file to download.
        - directory: DirectoryPath to compress and download.
        - apikey: API Key to authenticate the request.
        - token: API secret to authenticate the request.

    Returns:
        FileResponse:
        Returns the FileResponse object of the file.
    """
    await auth.level_2(request, apikey, token)
    if not any((filepath, directory)):
        LOGGER.error("No file or directory provided for download.")
        raise exceptions.HTTPException(
            status_code=HTTPStatus.BAD_REQUEST.real,
            detail="Either 'filepath' or 'directory' must be provided.",
        )
    LOGGER.info("Requested to download '%s'", filepath or directory)
    if directory:
        LOGGER.info("Compressing directory '%s' for download.", directory)
        tmp_directory = tempfile.gettempdir()
        filepath = zipper.archive(path=directory, directory=pathlib.Path(tmp_directory))
    mimetype = mimetypes.guess_type(filepath.name, strict=True)
    if mimetype:
        filetype = mimetype[0]
    else:
        filetype = "unknown"
    return StreamingResponse(
        iter_file_chunks(filepath=filepath, chunk_size=chunk_size),
        status_code=HTTPStatus.OK.real,
        media_type=filetype,
        headers={"Content-Disposition": f"attachment; filename={filepath.name}"},
    )
