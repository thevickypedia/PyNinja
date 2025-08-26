import mimetypes
import os
import pathlib
from collections.abc import Generator
from urllib.parse import quote

from init import NINJA_API_TIMEOUT, NINJA_API_URL, SESSION, urljoin


def run_command(command: str, timeout: int = NINJA_API_TIMEOUT, stream: bool = False):
    """Dispatches the command based on stream flag."""
    if stream:
        return run_command_stream(command, timeout)
    else:
        return run_command_json(command, timeout)


def run_command_json(command: str, timeout: int) -> dict:
    """Runs a command via the Ninja API and returns the JSON response."""
    payload = {"command": command, "timeout": timeout, "stream": False}
    url = urljoin(NINJA_API_URL, "/run-command")
    response = SESSION.post(url, json=payload)
    response.raise_for_status()
    return response.json()


def run_command_stream(command: str, timeout: int) -> Generator[str]:
    """Runs a command via the Ninja API and yields output lines as they are received."""
    payload = {"command": command, "timeout": timeout, "stream": True}
    url = urljoin(NINJA_API_URL, "/run-command")
    response = SESSION.post(url, json=payload, stream=True)
    response.raise_for_status()

    for line in response.iter_lines(decode_unicode=True):
        if line:
            yield line


def get_current_working_directory() -> str:
    """Gets the current working directory from the Ninja API."""
    json_response = run_command("pwd")
    stdout = json_response["stdout"]
    stderr = json_response["stderr"]
    if stderr:
        raise RuntimeError(f"Error getting current working directory: {stderr}")
    return stdout[0] if isinstance(stdout, list) else stdout


def download_file(filepath: str) -> None:
    """Downloads a file from Ninja API.

    Args:
        filepath: Filepath in the server.
    """
    url = urljoin(NINJA_API_URL, "/get-file")
    response = SESSION.post(url, json={"filepath": filepath})
    assert response.ok, response.text
    downloads = os.path.join(os.getcwd(), "downloads")
    os.makedirs(downloads, exist_ok=True)
    destination = os.path.join(downloads, os.path.basename(filepath))
    with open(destination, "wb") as file:
        file.write(response.content)
    print(f"File saved to {destination!r}")


def upload_file(filepath: str, destination: str = None, overwrite: bool = False) -> None:
    """Uploads a file to the Ninja API.

    Args:
        filepath: Path to the file to upload.
        destination: Destination directory on the server. Defaults to the current working directory.
        overwrite: Whether to overwrite the file if it already exists. Defaults to False.
    """
    url = urljoin(
        NINJA_API_URL,
        f"/put-file?directory={quote(destination) if destination else quote(get_current_working_directory())}"
        f"&overwrite={'true' if overwrite else 'false'}",
    )
    assert os.path.isfile(filepath), f"File {filepath} does not exist"
    with open(filepath, "rb") as f:
        files = {
            "file": (os.path.basename(filepath), f),
            "type": mimetypes.guess_type(filepath)[0],
        }
        response = SESSION.put(url, files=files)
        assert response.ok, response.text
        print(response.json())


def delete_content(filepath: str = None, directory: str = None, recursive: bool = False) -> None:
    """Deletes a file or directory from the Ninja API.

    Args:
        filepath: Path to the file or directory to delete.
        directory: Directory containing the file. Defaults to None.
        recursive: Whether to delete directories recursively. Defaults to False.
    """
    assert any((filepath, directory)), "Either filepath or directory must be provided"
    if directory and recursive:
        flag = input("Both directory path and recursive are set to True. Do you want to continue? [y/N]\n")
        if flag != "y":
            return
        print(f"Deleting directory: {directory!r} and all it's subdirectories.")
    url = urljoin(NINJA_API_URL, "/delete-content")
    response = SESSION.delete(url, json={"filepath": filepath, "directory": directory, "recursive": recursive})
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    pathlib.Path("keep").touch(exist_ok=True)
    upload_file("keep", overwrite=True)
    download_file("keep")
    delete_content("keep")
