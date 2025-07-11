"""Module to handle large file uploads in chunks via FastAPI with optional server-side unzip and checksum validation."""

import hashlib
import logging
import os
import shutil
from http import HTTPStatus
from typing import Optional

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth
from pyninja.features import zipper
from pyninja.modules import exceptions
from pyninja.routes import fullaccess

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def entry_fn(
    filename: str,
    filepath: str,
    tmp_filepath: str,
    directory: str,
    overwrite: bool = False,
    unzip: bool = False,
) -> None:
    """Entry function to handle the initial setup for large file upload."""
    if unzip:
        if not shutil.get_unpack_formats():
            raise exceptions.APIResponse(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR.real,
                detail="No unpack formats available, cannot unzip the file.",
            )
        # zip
        # tar
        # gztar (.tar.gz, .tgz)
        # bztar (.tar.bz2, .tbz)
        # xztar (.tar.xz, .txz)
        if not filename.endswith(
            (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz", ".tar.xz", ".txz")
        ):
            raise exceptions.APIResponse(
                status_code=HTTPStatus.BAD_REQUEST.real,
                detail="Unzip is only supported for zip and tar files.",
            )
    LOGGER.info(
        "Requested large file: '%s' for upload at %s",
        filename,
        directory,
    )
    if overwrite:
        os.remove(filepath) if os.path.isfile(filepath) else None
        os.remove(tmp_filepath) if os.path.isfile(tmp_filepath) else None
    elif os.path.isfile(filepath):
        LOGGER.warning("File '%s' already exists at '%s'", filename, directory)
        raise exceptions.APIResponse(
            status_code=HTTPStatus.BAD_REQUEST.real,
            detail=f"File {filename!r} exists at {str(directory)!r} already, "
            "set 'overwrite' flag to True to overwrite.",
        )
    fullaccess.create_directory(directory)


async def exit_fn(
    filename: str,
    filepath: str,
    tmp_filepath: str,
    directory: str,
    checksum: Optional[str],
    unzip: bool,
    delete_after_unzip: bool,
    iteration: int,
) -> None:
    """Exit function to finalize the large file upload."""
    if os.path.isfile(tmp_filepath):
        os.rename(tmp_filepath, filepath)
    else:
        raise exceptions.APIResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR.real,
            detail=f"Failed to store {filename!r} at {directory!r}",
        )
    LOGGER.info("File '%s' uploaded in %d chunks.", filename, iteration)
    if checksum:
        with open(filepath, "rb") as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        if checksum != checksum:
            LOGGER.critical("Checksum mismatch for file '%s'", filepath)
            raise exceptions.APIResponse(
                status_code=HTTPStatus.PARTIAL_CONTENT.real,
                detail=f"Checksum mismatch for file {filename!r}",
            )
        # Unzip will be skipped if checksum is not provided or does not match
        if unzip:
            try:
                filename = zipper.unarchive(zip_file=filepath, directory=directory)
                if delete_after_unzip:
                    os.remove(filepath)
                    LOGGER.info("File '%s' deleted after unzipping.", filepath)
            except (shutil.ReadError, OSError) as err:
                LOGGER.error("Error unzipping file '%s': %s", filepath, err)
                raise exceptions.APIResponse(
                    status_code=HTTPStatus.PARTIAL_CONTENT.real,
                    detail=f"File uploaded but failed to unzip: {err.__name__}",
                )
        raise exceptions.APIResponse(
            status_code=HTTPStatus.OK.real,
            detail=f"File {filename!r} was uploaded to {directory} in {iteration} chunks",
        )
    else:
        LOGGER.warning("Checksum was not provided.")
        raise exceptions.APIResponse(
            status_code=HTTPStatus.PARTIAL_CONTENT.real,
            detail=f"File {filename!r} was uploaded to {directory} in {iteration} chunks, "
            "but checksum was not provided.",
        )


async def put_large_file(
    request: Request,
    filename: str,
    directory: str,
    part_number: int = 0,
    is_last: bool = False,
    checksum: Optional[str] = None,
    overwrite: bool = False,
    unzip: bool = False,
    delete_after_unzip: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """API handler to upload a large file in chunks.

    Args:
        - request: Reference to the FastAPI request object.
        - filename: Incoming file's basename.
        - directory: Target directory for upload.
        - part_number: Incoming file part number.
        - is_last: Boolean flag to indicate that the incoming chunk is final.
        - checksum: Incoming file checksum.
        - overwrite: Boolean flag to remove existing file.
        - unzip: Boolean flag to unzip the file after upload.
        - delete_after_unzip: Boolean flag to delete the file after unzipping.
        - apikey: API Key to authenticate the request.
        - token: API secret to authenticate the request.
    """
    await auth.level_2(request, apikey, token)
    filepath = os.path.join(directory, filename)
    tmp_filepath = os.path.join(directory, f"{filename}.part")
    default = dict(
        filename=filename,
        directory=directory,
        filepath=filepath,
        tmp_filepath=tmp_filepath,
        unzip=unzip,
    )
    if part_number == 0:
        await entry_fn(overwrite=overwrite, **default)
    n = 0
    with open(tmp_filepath, "ab") as fstream:
        async for chunk in request.stream():
            n += 1
            fstream.write(chunk)
            fstream.flush()
    if is_last:
        await exit_fn(
            checksum=checksum,
            delete_after_unzip=delete_after_unzip,
            iteration=n,
            **default,
        )
    else:
        LOGGER.info("File '%s' uploaded in %d chunks.", filename, n)
        return exceptions.APIResponse(
            status_code=HTTPStatus.ACCEPTED.real,
            detail=f"File [{filename}:{part_number}] uploaded in {n} chunks.",
        )
