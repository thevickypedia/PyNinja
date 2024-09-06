import ast
import asyncio
import base64
import logging
import secrets
import subprocess
import time
from datetime import datetime
from http import HTTPStatus
from typing import Dict, List, Optional

import jinja2
import psutil
from fastapi import Depends, Header, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
)
from fastapi.websockets import WebSocket, WebSocketDisconnect, WebSocketState
from pydantic import PositiveFloat, PositiveInt

from pyninja import (
    auth,
    dockerized,
    exceptions,
    models,
    process,
    rate_limit,
    service,
    squire,
)

LOGGER = logging.getLogger("uvicorn.default")
BASIC_AUTH = HTTPBasic()
BEARER_AUTH = HTTPBearer()


async def get_ip(
    request: Request,
    public: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """Get local and public IP address of the device.

    Args:
        request: Reference to the FastAPI request object.
        public: Boolean flag to get the public IP address.
        apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and the public/private IP as response.
    """
    await auth.level_1(request, apikey)
    if public:
        return squire.public_ip_address()
    else:
        return squire.private_ip_address()


async def get_cpu(
    request: Request,
    interval: int | float = 2,
    per_cpu: bool = True,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """Get the CPU utilization.

    **Args:**

        request: Reference to the FastAPI request object.
        interval: Interval to get the CPU utilization.
        per_cpu: If True, returns the CPU utilization for each CPU.
        apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and CPU usage as response.
    """
    await auth.level_1(request, apikey)
    if per_cpu:
        cpu_percentages = psutil.cpu_percent(interval=interval, percpu=True)
        usage = {f"cpu{i + 1}": percent for i, percent in enumerate(cpu_percentages)}
    else:
        usage = {"cpu": psutil.cpu_percent(interval=interval, percpu=False)}
    raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=usage)


async def get_memory(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """Get memory utilization.

    **Args:**

        request: Reference to the FastAPI request object.
        apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and CPU usage as response.
    """
    await auth.level_1(request, apikey)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.OK.real,
        detail={
            "ram_total": squire.size_converter(psutil.virtual_memory().total),
            "ram_used": squire.size_converter(psutil.virtual_memory().used),
            "ram_usage": psutil.virtual_memory().percent,
            "swap_total": squire.size_converter(psutil.swap_memory().total),
            "swap_used": squire.size_converter(psutil.swap_memory().used),
            "swap_usage": psutil.swap_memory().percent,
        },
    )


async def run_command(
    request: Request,
    payload: models.Payload,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
    token: Optional[str] = Header(None),
):
    """**API function to run a command on host machine.**

    **Args:**

        request: Reference to the FastAPI request object.
        payload: Payload received as request body.
        apikey: API Key to authenticate the request.
        token: API secret to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_2(request, apikey, token)
    LOGGER.info(
        "Requested command: '%s' with timeout: %ds", payload.command, payload.timeout
    )
    try:
        response = squire.process_command(payload.command, payload.timeout)
    except subprocess.TimeoutExpired as warn:
        LOGGER.warning(warn)
        raise exceptions.APIResponse(
            status_code=HTTPStatus.REQUEST_TIMEOUT, detail=warn.__str__()
        )
    raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=response)


async def process_status(
    request: Request,
    process_name: str,
    cpu_interval: PositiveInt | PositiveFloat = 1,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to monitor a process.**

    **Args:**

        request: Reference to the FastAPI request object.
        process_name: Name of the process to check status.
        cpu_interval: Interval in seconds to get the CPU usage.
        apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if response := process.get_process_status(process_name, cpu_interval):
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=response)
    LOGGER.error("%s: 404 - No such process", process_name)
    raise exceptions.APIResponse(
        status_code=404, detail=f"Process {process_name} not found."
    )


async def service_status(
    request: Request,
    service_name: str,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to monitor a service.**

    **Args:**

        request: Reference to the FastAPI request object.
        service_name: Name of the service to check status.
        apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    response = service.get_service_status(service_name)
    LOGGER.info(
        "%s: %d - %s",
        service_name,
        response.status_code,
        response.description,
    )
    raise exceptions.APIResponse(
        status_code=response.status_code, detail=response.description
    )


async def docker_containers(
    request: Request,
    container_name: str = None,
    get_all: bool = False,
    get_running: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get docker containers' information.**

    **Args:**

        request: Reference to the FastAPI request object.
        container_name: Name of the container to check status.
        get_all: Get all the containers' information.
        get_running: Get running containers' information.
        apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if get_all:
        if all_containers := dockerized.get_all_containers():
            raise exceptions.APIResponse(
                status_code=HTTPStatus.OK.real, detail=all_containers
            )
        raise exceptions.APIResponse(
            status_code=HTTPStatus.NOT_FOUND.real, detail="No containers found!"
        )
    if get_running:
        if running_containers := list(dockerized.get_running_containers()):
            raise exceptions.APIResponse(
                status_code=HTTPStatus.OK.real, detail=running_containers
            )
        raise exceptions.APIResponse(
            status_code=HTTPStatus.NOT_FOUND.real, detail="No running containers found!"
        )
    if container_name:
        if container_status := dockerized.get_container_status(container_name):
            raise exceptions.APIResponse(
                status_code=HTTPStatus.OK.real, detail=container_status
            )
        raise exceptions.APIResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
            detail="Unable to get container status!",
        )
    raise exceptions.APIResponse(
        status_code=HTTPStatus.BAD_REQUEST.real,
        detail="Either 'container_name' or 'get_all' or 'get_running' should be set",
    )


async def docker_images(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get docker images' information.**

    **Args:**

        request: Reference to the FastAPI request object.
        apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if images := dockerized.get_all_images():
        LOGGER.info(images)
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=images)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
        detail="Unable to get docker images!",
    )


async def docker_volumes(
    request: Request,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**API function to get docker volumes' information.**

    **Args:**

        request: Reference to the FastAPI request object.
        apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and detail as response.
    """
    await auth.level_1(request, apikey)
    if volumes := dockerized.get_all_volumes():
        LOGGER.info(volumes)
        raise exceptions.APIResponse(status_code=HTTPStatus.OK.real, detail=volumes)
    raise exceptions.APIResponse(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE.real,
        detail="Unable to get docker volumes!",
    )


async def docs() -> RedirectResponse:
    """Redirect to docs page.

    Returns:
        RedirectResponse:
        Redirects the user to ``/docs`` page.
    """
    return RedirectResponse("/docs")


async def health():
    """Health check for PyNinja.

    Returns:
        APIResponse:
        Returns a health check response with status code 200.
    """
    raise exceptions.APIResponse(status_code=HTTPStatus.OK, detail=HTTPStatus.OK.phrase)


def verify_monitor_creds(
    request: Request, credentials: HTTPBasicCredentials = Depends(BASIC_AUTH)
):
    """Verify credentials for monitoring page.

    Args:
        request: Reference to the FastAPI request object.
        credentials: Basic authentication object.
    """
    username = models.env.monitor_username and secrets.compare_digest(
        credentials.username, models.env.monitor_username
    )
    password = models.env.monitor_password and secrets.compare_digest(
        credentials.password, models.env.monitor_password
    )
    if username and password:
        LOGGER.info(
            "Connection received from client-host: %s, host-header: %s, x-fwd-host: %s",
            request.client.host,
            request.headers.get("host"),
            request.headers.get("x-forwarded-host"),
        )
        if user_agent := request.headers.get("user-agent"):
            LOGGER.info("User agent: %s", user_agent)
    else:
        raise exceptions.APIResponse(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )


def generate_cookie(request: Request) -> Dict[str, str | bool | int]:
    """Generate a cookie for monitoring page.

    Args:
        request: Reference to the FastAPI request object.

    Returns:
        Dict[str, str | bool | int]:
        Returns a dictionary with cookie details
    """
    client_token = dict(token=squire.keygen(), timestamp=int(time.time()))
    models.ws_session.client_auth[request.client.host] = client_token
    encoded_token = str(client_token).encode("ascii")
    auth_payload = base64.b64encode(encoded_token).decode("ascii")
    expiration = int(time.time()) + models.env.monitor_session
    return dict(
        key="session_token",
        value=auth_payload,
        samesite="strict",
        path="/",
        httponly=False,  # Set to False explicitly, for WebSocket
        expires=expiration,
    )


def validate_session(host: str, cookie_string: str) -> bool:
    """Validate the session token.

    Args:
        host: Hostname from the request.
        cookie_string: Session token from the cookie.

    Returns:
        bool:
        Returns True if the session token is valid.
    """
    if not cookie_string:
        LOGGER.warning("No session token found for %s", host)
        return False
    try:
        decoded_payload = base64.b64decode(cookie_string)
        decoded_str = decoded_payload.decode("ascii")
        original_dict = ast.literal_eval(decoded_str)
        assert (
            models.ws_session.client_auth.get(host) == original_dict
        ), f"{original_dict} != {models.ws_session.client_auth.get(host)}"
        poached = datetime.fromtimestamp(
            original_dict.get("timestamp") + models.env.monitor_session
        )
        LOGGER.info(
            "Session token validated for %s until %s",
            host,
            poached.strftime("%Y-%m-%d %H:%M:%S"),
        )
        return True
    except (KeyError, ValueError, TypeError) as error:
        LOGGER.critical(error)
    except AssertionError as error:
        LOGGER.error("Session token mismatch: %s", error)
    return False


async def logout(request: Request):
    """Logout the user from the monitoring page.

    Args:
        request: Reference to the FastAPI request object.

    Returns:
        RedirectResponse:
        Redirects the user to the monitoring page.
    """
    # todo:
    #  - This is a joke, replace the whole thing with proper session management
    #  - Remove HTTPBasic auth
    models.ws_session.client_auth.pop(request.client.host, None)
    response = RedirectResponse("/monitor")
    response.delete_cookie("session_token")
    response.headers["authorization"] = "Basic"
    return response


async def monitor(request: Request):
    """Renders the UI for monitoring page.

    Args:
        request: Reference to the FastAPI request object.

    Returns:
        HTMLResponse:
        Returns an HTML response templated using Jinja2.
    """
    with open(models.ws_settings.template) as file:
        template_file = file.read()
    template = jinja2.Template(template_file)
    rendered = template.render(
        HOST=models.env.ninja_host,
        PORT=models.env.ninja_port,
        DEFAULT_CPU_INTERVAL=models.ws_settings.cpu_interval,
        DEFAULT_REFRESH_INTERVAL=models.ws_settings.refresh_interval,
    )
    response = HTMLResponse(rendered)
    cookie_data = generate_cookie(request)
    response.set_cookie(**cookie_data)
    return response


async def websocket_endpoint(websocket: WebSocket):
    """Websocket endpoint to fetch live system resource usage.

    Args:
        websocket: Reference to the websocket object.
    """
    await websocket.accept()
    session_token = websocket.cookies.get("session_token") or websocket.headers.get(
        "cookie", {}
    ).get("session_token")
    if not validate_session(websocket.client.host, session_token):
        await websocket.send_text("Unauthorized")
        await websocket.close()
        return
    refresh_time = time.time()
    LOGGER.info(
        "Intervals: {'CPU': %s, 'refresh': %s}",
        models.ws_settings.cpu_interval,
        models.ws_settings.refresh_interval,
    )
    data = squire.system_resources(models.ws_settings.cpu_interval)
    while True:
        if websocket.application_state == WebSocketState.CONNECTED:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                if msg.startswith("refresh_interval:"):
                    models.ws_settings.refresh_interval = int(msg.split(":")[1].strip())
                    LOGGER.info(
                        "Updating refresh interval to %s seconds",
                        models.ws_settings.refresh_interval,
                    )
                elif msg.startswith("cpu_interval"):
                    models.ws_settings.cpu_interval = int(msg.split(":")[1].strip())
                    LOGGER.info(
                        "Updating CPU interval to %s seconds",
                        models.ws_settings.cpu_interval,
                    )
                else:
                    LOGGER.error("Invalid WS message received: %s", msg)
                    break
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break
        now = time.time()
        if (
            now
            - models.ws_session.client_auth.get(websocket.client.host).get("timestamp")
            > models.env.monitor_session
        ):
            LOGGER.info("Session expired for %s", websocket.client.host)
            await websocket.send_text("Session Expired")
            await websocket.close()
            break
        if now - refresh_time > models.ws_settings.refresh_interval:
            refresh_time = time.time()
            LOGGER.debug("Fetching new charts")
            data = squire.system_resources(models.ws_settings.cpu_interval)
        try:
            await websocket.send_json(data)
            await asyncio.sleep(1)
        except WebSocketDisconnect:
            break


def get_all_routes() -> List[APIRoute]:
    """Get all the routes to be added for the API server.

    Returns:
        List[APIRoute]:
        Returns the routes as a list of APIRoute objects.
    """
    dependencies = [
        Depends(dependency=rate_limit.RateLimiter(each_rate_limit).init)
        for each_rate_limit in models.env.rate_limit
    ]
    routes = [
        APIRoute(path="/", endpoint=docs, methods=["GET"], include_in_schema=False),
        APIRoute(
            path="/health", endpoint=health, methods=["GET"], include_in_schema=False
        ),
        APIRoute(
            path="/monitor",
            endpoint=monitor,
            methods=["GET"],
            dependencies=[Depends(verify_monitor_creds)] + dependencies,
        ),
        APIRoute(
            path="/logout",
            endpoint=logout,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIWebSocketRoute(path="/ws/system", endpoint=websocket_endpoint),
        APIRoute(
            path="/get-ip",
            endpoint=get_ip,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-cpu",
            endpoint=get_cpu,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/get-memory",
            endpoint=get_memory,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/service-status",
            endpoint=service_status,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/process-status",
            endpoint=process_status,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-container",
            endpoint=docker_containers,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-image",
            endpoint=docker_images,
            methods=["GET"],
            dependencies=dependencies,
        ),
        APIRoute(
            path="/docker-volume",
            endpoint=docker_volumes,
            methods=["GET"],
            dependencies=dependencies,
        ),
    ]
    if all((models.env.remote_execution, models.env.api_secret)):
        routes.append(
            APIRoute(
                path="/run-command",
                endpoint=run_command,
                methods=["POST"],
                dependencies=dependencies,
            )
        )
    return routes
