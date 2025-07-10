import asyncio
import copy
import mimetypes
import os
import pathlib
from collections.abc import AsyncIterable
from urllib.parse import quote

import aiohttp
import dotenv
import requests

dotenv.load_dotenv(dotenv.find_dotenv())

NINJA_API_KEY = os.environ["NINJA_APIKEY"]
NINJA_API_URL = os.environ["NINJA_API_URL"]
NINJA_API_TIMEOUT = os.environ["NINJA_API_TIMEOUT"]
NINJA_API_TOKEN = os.environ["NINJA_API_TOKEN"]

SESSION = requests.Session()
SESSION.headers = {
    "Authorization": f"Bearer {NINJA_API_KEY}",
    "Token": NINJA_API_TOKEN,
    "Accept": "application/json",
}


def urljoin(*args) -> str:
    """Joins given arguments into a url. Trailing but not leading slashes are stripped for each argument.

    Returns:
        str:
        Joined url.
    """
    return "/".join(map(lambda x: str(x).rstrip("/").lstrip("/"), args))


def run_command(command: str, timeout: int = NINJA_API_TIMEOUT) -> dict:
    """Runs a command on the Ninja API.

    Args:
        command (str): The command to run.
        timeout (int): Timeout for the command execution in seconds.

    Returns:
        dict: A dictionary containing the command output and error messages.
    """
    payload = {"command": command, "timeout": timeout}
    url = urljoin(NINJA_API_URL, "/run-command")
    response = SESSION.post(url, json=payload)
    response.raise_for_status()
    return response.json()


def get_current_working_directory() -> str:
    """Gets the current working directory from the Ninja API."""
    json_response = run_command("pwd")
    stdout = json_response["stdout"]
    stderr = json_response["stderr"]
    if stderr:
        raise RuntimeError(f"Error getting current working directory: {stderr}")
    return stdout[0] if isinstance(stdout, list) else stdout


def upload_file(
        filepath: str,
        destination: str = None,
        overwrite: bool = False
) -> None:
    """Uploads a file to the Ninja API.

    Args:
        filepath (str): Path to the file to upload.
        destination (str, optional): Destination directory on the server. Defaults to the current working directory.
        overwrite (bool, optional): Whether to overwrite the file if it already exists. Defaults to False.
    """
    url = urljoin(
        NINJA_API_URL,
        f"/put-file?directory={quote(destination) if destination else quote(get_current_working_directory())}"
        f"&overwrite={'true' if overwrite else 'false'}"
    )
    assert os.path.isfile(filepath), f"File {filepath} does not exist"
    with open(filepath, "rb") as f:
        files = {"file": (os.path.basename(filepath), f), "type": mimetypes.guess_type(filepath)[0]}
        response = SESSION.put(url, files=files)
        assert response.ok, response.text
        print(response.json())


def delete_content(
        filepath: str = None,
        directory: str = None,
        recursive: bool = False
) -> None:
    """Deletes a file or directory from the Ninja API.

    Args:
        filepath (str): Path to the file or directory to delete.
        directory (str, optional): Directory containing the file. Defaults to None.
        recursive (bool, optional): Whether to delete directories recursively. Defaults to False.
    """
    assert any((filepath, directory)), "Either filepath or directory must be provided"
    url = urljoin(NINJA_API_URL, "/delete-content")
    response = SESSION.delete(url, json={"filepath": filepath, "directory": directory, "recursive": recursive})
    response.raise_for_status()
    print(response.json())


async def upload_large_file(
        file_path: str,
        directory: str,
        overwrite: bool = False
):
    """Uploads a large file to the Ninja API using aiohttp."""
    assert os.path.isfile(file_path), f"File {file_path} does not exist"
    url = urljoin(
        NINJA_API_URL,
        f"/put-large-file"
    )
    filename = os.path.basename(file_path)
    params = {"directory": directory, "filename": filename}
    headers = copy.deepcopy(SESSION.headers)
    headers["Content-Type"] = "application/octet-stream"
    async with aiohttp.ClientSession() as session:
        with open(file_path, "rb") as fstream:
            async with session.put(
                url=url,
                params=params,
                data=fstream,
                headers=headers,
            ) as response:
                response.raise_for_status()
                print(await response.json())


if __name__ == '__main__':
    pathlib.Path(".keep").touch(exist_ok=True)
    upload_file(".keep", overwrite=True)
    delete_content(".keep")
    asyncio.run(upload_large_file(
        # Client side path (source)
        file_path=os.path.join(os.path.expanduser("~"), "Desktop", "png.zip"),
        # Server side path (destination)
        directory=os.path.join(get_current_working_directory(), "tmp"),
        overwrite=True,
    ))
