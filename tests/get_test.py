import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from multiprocessing import Process
from typing import Any, Dict, List, NoReturn

import dotenv
import requests

from pyninja.modules.enums import APIEndpoints

path = dotenv.find_dotenv()
dotenv.load_dotenv(path)

apikey = os.environ["APIKEY"]
urls = list(map(str.strip, os.environ["TEST_URLS"].split(",")))


@dataclass
class Payload:
    """Class to represent the payload for API requests."""

    params: Dict[str, Any] | None = None
    status: List[int] | None = None


def make_request(host: str, endpoint: APIEndpoints, payload: Payload) -> None | NoReturn:
    """Make a GET request to the specified endpoint with the given payload."""
    response = requests.get(
        f"{host}{endpoint.value}", params=payload.params, headers={"Authorization": f"Bearer {apikey}"}
    )
    assert (
        response.status_code in payload.status
    ), f"Failed to GET {host}{endpoint} with params {payload.params}: [{response.status_code}:{response.text}]"


def test_get_endpoints(host: str) -> None | NoReturn:
    """Test all GET endpoints with various payloads and expected status codes."""
    endpoints = {
        APIEndpoints.get_ip: [
            Payload(params={"public": True}, status=[200]),
            Payload(params={"public": False}, status=[200]),
        ],
        APIEndpoints.get_cpu: [
            Payload(params={"interval": 0.1, "per_cpu": True}, status=[200]),
            Payload(params={"interval": 0.1, "per_cpu": False}, status=[200]),
        ],
        APIEndpoints.get_cpu_load: [Payload(status=[200])],
        APIEndpoints.get_processor: [Payload(status=[200])],
        APIEndpoints.get_memory: [Payload(status=[200])],
        APIEndpoints.get_disk_utilization: [
            Payload(params={"path": "/"}, status=[200]),
            Payload(params={"path": uuid.uuid4().hex}, status=[400]),
        ],
        APIEndpoints.get_all_disks: [Payload(status=[200])],
        APIEndpoints.get_all_services: [Payload(status=[200])],
        APIEndpoints.get_service_status: [Payload(params={"service_name": "PyNinja"}, status=[200, 404])],
        APIEndpoints.get_service_usage: [Payload(params={"service_name": "PyNinja"}, status=[200, 404])],
        APIEndpoints.get_process_status: [Payload(params={"process_name": "python"}, status=[200, 404])],
        APIEndpoints.get_process_usage: [
            Payload(params={"process_name": "python", "cpu_interval": 0.1}, status=[200, 404])
        ],
        APIEndpoints.get_docker_containers: [Payload(params={"get_all": True}, status=[200, 404])],
        APIEndpoints.get_docker_images: [Payload(status=[200, 503])],
        APIEndpoints.get_docker_volumes: [Payload(status=[200, 503])],
        APIEndpoints.get_docker_stats: [Payload(status=[200, 503])],
        APIEndpoints.get_certificates: [Payload(status=[200, 403, 417])],
    }
    with ThreadPoolExecutor() as executor:
        futures = []
        for endpoint, payloads in endpoints.items():
            for payload in payloads:
                futures.append(executor.submit(make_request, host, endpoint, payload))
        for future in as_completed(futures):
            try:
                future.result()
            except AssertionError as error:
                print(error.with_traceback(error.__traceback__))
                os._exit(1)


if __name__ == "__main__":
    procs = []
    for url in urls:
        print(f"Testing GET routes on {url}")
        procs.append(Process(target=test_get_endpoints, args=(url,)))
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join()
