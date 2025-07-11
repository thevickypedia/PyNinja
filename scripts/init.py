import os

import dotenv
import requests

dotenv.load_dotenv(dotenv.find_dotenv())

NINJA_API_KEY = os.environ["NINJA_APIKEY"]
NINJA_API_URL = os.environ["NINJA_API_URL"]
NINJA_API_TIMEOUT = os.environ["NINJA_API_TIMEOUT"]
NINJA_API_TOKEN = os.environ["NINJA_API_TOKEN"]
CHUNK_SIZE = 9 * 1024 * 1024  # 9MB

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
