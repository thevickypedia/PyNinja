import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from multiprocessing import Process
from typing import Any, Dict, List, NoReturn

import dotenv
import pyotp
import requests

from pyninja.modules.enums import APIEndpoints

path = dotenv.find_dotenv()
dotenv.load_dotenv(path)

apikey = os.environ["APIKEY"]
api_secret = os.environ["API_SECRET"]
auth_token = os.environ["AUTHENTICATOR_TOKEN"]
urls = list(map(str.strip, os.environ["TEST_URLS"].split(",")))


get_totp = lambda: pyotp.TOTP(auth_token).now()  # noqa: E731


@dataclass
class Payload:
    """Class to represent the payload for API requests."""

    data: Dict[str, Any] | None = None
    params: Dict[str, Any] | None = None
    status: List[int] | None = None


def make_request(host: str, endpoint: APIEndpoints, payload: Payload, mfa_code: str) -> None | NoReturn:
    """Make a POST request to the specified endpoint with the given payload."""
    response = requests.post(
        f"{host}{endpoint.value}",
        params=payload.params,
        json=payload.data,
        headers={"Authorization": f"Bearer {apikey}", "API-SECRET": api_secret, "MFA-CODE": mfa_code},
    )
    assert response.status_code in payload.status, (
        f"Failed to POST {host}{endpoint} with params {payload.data or payload.params}: "
        f"[{response.status_code}:{response.text}]"
    )


def test_post_endpoints(host: str) -> None | NoReturn:
    """Test all POST endpoints with various payloads and expected status codes."""
    endpoints = {
        APIEndpoints.run_command: [
            Payload(data={"command": "pwd", "shell": True}, status=[200]),
            Payload(data={"command": uuid.uuid4().hex}, status=[200]),
        ],
        APIEndpoints.stop_service: [Payload(params={"service_name": uuid.uuid4().hex}, status=[200, 404])],
        APIEndpoints.start_service: [Payload(params={"service_name": uuid.uuid4().hex}, status=[200, 404])],
        APIEndpoints.restart_service: [Payload(params={"service_name": uuid.uuid4().hex}, status=[200, 404])],
        APIEndpoints.stop_docker_container: [Payload(params={"container_name": uuid.uuid4().hex}, status=[404])],
        APIEndpoints.start_docker_container: [Payload(params={"container_name": uuid.uuid4().hex}, status=[404])],
        APIEndpoints.list_files: [
            Payload(data={"directory": ".", "show_hidden_files": True, "deep_scan": True}, status=[200])
        ],
        APIEndpoints.get_file: [Payload(data={"filepath": uuid.uuid4().hex}, status=[404, 422])],
    }
    mfa_code = get_totp()
    with ThreadPoolExecutor() as executor:
        futures = []
        for endpoint, payloads in endpoints.items():
            for payload in payloads:
                futures.append(executor.submit(make_request, host, endpoint, payload, mfa_code))
        for future in as_completed(futures):
            try:
                future.result()
            except AssertionError as error:
                print(error.with_traceback(error.__traceback__))
                os._exit(1)


if __name__ == "__main__":
    procs = []
    for url in urls:
        print(f"Testing POST routes on {url}")
        procs.append(Process(target=test_post_endpoints, args=(url,)))
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join()
