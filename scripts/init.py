import math
import os

import dotenv
import requests

dotenv.load_dotenv(dotenv.find_dotenv())

NINJA_API_KEY = os.environ["NINJA_APIKEY"]
NINJA_API_URL = os.environ["NINJA_API_URL"]
NINJA_API_TIMEOUT = os.environ["NINJA_API_TIMEOUT"]
NINJA_API_SECRET = os.environ["NINJA_API_SECRET"]
SERVER_PASSWORD = os.getenv("SERVER_PASSWORD")
CHUNK_SIZE = 9 * 1024 * 1024 * 10  # 90MB

SESSION = requests.Session()
SESSION.headers = {
    "Authorization": f"Bearer {NINJA_API_KEY}",
    "API-SECRET": NINJA_API_SECRET,
    "Accept": "application/json",
}

format_nos = lambda input_: (  # noqa: E731
    int(input_) if isinstance(input_, float) and input_.is_integer() else input_
)


def urljoin(*args) -> str:
    """Joins given arguments into a url. Trailing but not leading slashes are stripped for each argument.

    Returns:
        str:
        Joined url.
    """
    return "/".join(map(lambda x: str(x).rstrip("/").lstrip("/"), args))


def size_converter(byte_size: int | float) -> str:
    """Gets the current memory consumed and converts it to human friendly format.

    Args:
        byte_size: Receives byte size as argument.

    Returns:
        str:
        Converted human-readable size.
    """
    if byte_size:
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        index = int(math.floor(math.log(byte_size, 1024)))
        return (
            f"{format_nos(round(byte_size / pow(1024, index), 2))} {size_name[index]}"
        )
    return "0 B"
