import asyncio
import mimetypes
import os
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


def upload_file(filepath: str, destination: str = None, overwrite: bool = False) -> None:
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
        response = SESSION.post(url, files=files)
        assert response.ok, response.text
        print(response.json())


def delete_content(filepath: str, directory: str = None, recursive: bool = False) -> None:
    """Deletes a file or directory from the Ninja API.

    Args:
        filepath (str): Path to the file or directory to delete.
        directory (str, optional): Directory containing the file. Defaults to None.
        recursive (bool, optional): Whether to delete directories recursively. Defaults to False.
    """
    url = urljoin(NINJA_API_URL, "/delete-content")
    response = SESSION.delete(url, json={"filepath": filepath, "directory": directory, "recursive": recursive})
    response.raise_for_status()
    print(response.json())


async def upload_large_file(
        file_path: str,
        directory: str,
        chunk_size: int = 1024 * 1024 * 5,  # 5MB default chunk size
        overwrite: bool = False,
):
    filename = os.path.basename(file_path)
    url = urljoin(
        NINJA_API_URL, f"/put-large-file?filename={quote(filename)}"
    )
    params = {
        "directory": directory,
        "overwrite": str(overwrite).lower(),
        "chunk_size": chunk_size,
    }
    async with aiohttp.ClientSession() as session:
        with open(file_path, "rb") as f:
            async with session.post(
                    url,
                    params=params,
                    data={"file": f},
                    headers=SESSION.headers,
            ) as resp:
                return await resp.json()


if __name__ == '__main__':
    filepath_ = os.path.join(os.getcwd(), ".keep")
    upload_file(str(filepath_), overwrite=True)
    delete_content(str(filepath_))
    run_command("touch scripts/.keep")
    asyncio.run(upload_large_file(
        file_path=os.path.join(os.path.expanduser("~"), "Desktop", "png.zip"),
        directory=os.getcwd(),
        chunk_size=1024 * 1024 * 5,  # 5MB
        overwrite=True,
    ))
