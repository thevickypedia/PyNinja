import asyncio
import copy
import hashlib
import os
import pathlib

import aiohttp
from init import CHUNK_SIZE, NINJA_API_URL, SESSION, size_converter, urljoin
from tqdm import tqdm
from zipper import archive


async def upload_large_file(
    directory: str,
    dir_path: str = None,
    file_path: str = None,
    overwrite: bool = False,
):
    """Uploads a large file to the Ninja API server in chunks.

    Args:
        directory: Directory on the server where the file will be uploaded.
        dir_path: Directory path to upload.
        file_path: File path to the large file to upload.
        overwrite: Boolean flag to overwrite existing files.
    """
    assert any((dir_path, file_path)), "Either dir_path or file_path must be provided"
    if dir_path:
        file_path = archive(pathlib.Path(dir_path))
    assert os.path.isfile(file_path), f"File {file_path} does not exist"
    url = urljoin(NINJA_API_URL, "/put-large-file")
    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Uploading {filename!r} of size: {size_converter(file_size)} to {directory!r}")
    print(f"Total chunks: {total_chunks}")

    # Calculate checksum in advance (optional, but good for validation)
    with open(file_path, "rb") as f:
        checksum = hashlib.md5(f.read()).hexdigest()

    headers = copy.deepcopy(SESSION.headers)
    headers["Content-Type"] = "application/octet-stream"
    overwrite = str(overwrite).lower()
    is_zipfile = str(dir_path is not None or file_path.endswith(".zip")).lower()

    async with aiohttp.ClientSession() as session:
        with (
            open(file_path, "rb") as fstream,
            tqdm(total=total_chunks, unit="chunk", desc=f"Uploading {filename}") as pbar,
        ):
            for part_number in range(total_chunks):
                chunk = fstream.read(CHUNK_SIZE)
                is_last = part_number == total_chunks - 1
                params = dict(
                    directory=directory,
                    filename=filename,
                    part_number=part_number,
                    is_last=str(is_last).lower(),
                    overwrite=overwrite,
                    unzip=is_zipfile,
                    delete_after_unzip=is_zipfile,
                )
                if is_last:
                    params["checksum"] = checksum
                async with session.put(
                    url,
                    params=params,
                    data=chunk,
                    headers=headers,
                ) as response:
                    assert response.ok, await response.text()
                pbar.update(1)
                await asyncio.sleep(0.1)  # prevent server overload (tune as needed)


async def download_large_file(filepath: str = None, directory: str = None, destination: str = None):
    """Downloads a large file from the given URL in chunks.

    Args:
        filepath: Server-side path to the file to download.
        directory: Server-side path to the directory to download.
        destination: Destination path to save the downloaded file.
    """
    assert any((filepath, directory)), "Either filepath or directory must be provided"
    url = urljoin(NINJA_API_URL, "/get-large-file")
    params = dict(
        filepath=filepath,
        directory=directory,
        chunk_size=CHUNK_SIZE,
    )
    if filepath:
        destination = os.path.join(destination or pathlib.Path(__file__).parent, os.path.basename(filepath))
    else:
        destination = os.path.join(
            destination or pathlib.Path(__file__).parent,
            os.path.basename(directory) + ".zip",
        )
    with SESSION.get(url, stream=True, params=params) as response:
        response.raise_for_status()
        with open(destination, "wb") as fstream:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    fstream.write(chunk)
                else:
                    print("Received empty chunk, stopping download.")
                    break


if __name__ == "__main__":
    asyncio.run(
        upload_large_file(
            # Client side path (source)
            file_path=os.environ.get("UPLOAD_FILEPATH"),
            dir_path=os.environ.get("UPLOAD_DIRECTORY"),
            # Server side path (destination)
            directory=os.environ["SERVER_DESTINATION"],
            overwrite=True,
        )
    )
    asyncio.run(
        download_large_file(
            # Server side path (source)
            filepath=os.environ.get("DOWNLOAD_FILEPATH"),
            directory=os.environ.get("DOWNLOAD_DIRECTORY"),
        )
    )
