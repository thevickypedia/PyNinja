import asyncio
import logging
import platform
import shutil
import time
from datetime import timedelta
from http import HTTPStatus

import psutil
from fastapi import Cookie, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.websockets import WebSocket, WebSocketDisconnect

from .. import disks, exceptions, gpu, models, monitor, processor, squire, version
from . import resources

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def error_endpoint(request: Request) -> HTMLResponse:
    """Error endpoint for the monitoring page.

    Args:
        request: Reference to the FastAPI request object.

    Returns:
        HTMLResponse:
        Returns an HTML response templated using Jinja2.
    """
    return await monitor.config.clear_session(
        monitor.config.templates.TemplateResponse(
            name="unauthorized.html",
            context={
                "request": request,
                "signin": "/login",
                "version": f"v{version.__version__}",
            },
        )
    )


async def logout_endpoint(request: Request) -> HTMLResponse:
    """Logs out the user and clears the session token.

    Args:
        request: Reference to the FastAPI request object.

    Returns:
        HTMLResponse:
        Redirects to login page.
    """
    session_token = request.cookies.get("session_token")
    try:
        await monitor.authenticator.validate_session(request.client.host, session_token)
    except exceptions.SessionError as error:
        response = await monitor.authenticator.session_error(request, error)
    else:
        models.ws_session.client_auth.pop(request.client.host)
        response = monitor.config.templates.TemplateResponse(
            name="logout.html",
            context={
                "request": request,
                "signin": "/login",
                "detail": "You have been logged out successfully.",
                "show_login": False,
                "version": f"v{version.__version__}",
            },
        )
    return await monitor.config.clear_session(response)


async def login_endpoint(
    request: Request, authorization: HTTPAuthorizationCredentials = Depends(BEARER_AUTH)
) -> JSONResponse:
    """Login endpoint for the monitoring page.

    Returns:
        JSONResponse:
        Returns a JSONResponse object with a ``session_token`` and ``redirect_url`` set.
    """
    auth_payload = await monitor.authenticator.verify_login(
        authorization, request.client.host
    )
    # AJAX calls follow redirect and return the response instead of replacing the URL
    # Solution is to revert to Form, but that won't allow header auth and additional customization done by JavaScript
    response = JSONResponse(
        content={"redirect_url": "/monitor"},
        status_code=HTTPStatus.OK,
    )
    response.set_cookie(**await monitor.authenticator.generate_cookie(auth_payload))
    return response


async def monitor_endpoint(request: Request, session_token: str = Cookie(None)):
    """Renders the UI for monitoring page.

    Args:
        request: Reference to the FastAPI request object.
        session_token: Session token set after verifying username and password.

    Returns:
        HTMLResponse:
        Returns an HTML response templated using Jinja2.
    """
    # Removes the first hostname from client_auth quietly
    if len(models.ws_session.client_auth) > models.env.max_connections:
        first_key = next(iter(models.ws_session.client_auth))
        # Remove the key-value pair associated with the first authenticated user
        LOGGER.info(
            "Maximum parallel connections limit reached. Dropping %s", first_key
        )
        models.ws_session.client_auth.pop(first_key, None)
    if session_token:
        try:
            await monitor.authenticator.validate_session(
                request.client.host, session_token
            )
        except exceptions.SessionError as error:
            LOGGER.error("Session token mismatch: %s", error)
            return await monitor.config.clear_session(
                await monitor.authenticator.session_error(request, error)
            )
        else:
            uname = platform.uname()
            sys_info_basic = {
                "System": uname.system,
                "Architecture": uname.machine,
                "Node": uname.node,
                "CPU Cores": psutil.cpu_count(logical=True),
                "Uptime": squire.format_timedelta(
                    timedelta(seconds=time.time() - psutil.boot_time())
                ),
            }
            if gpu_names := gpu.get_names():
                LOGGER.info(gpu_names)
                sys_info_basic["GPU"] = ", ".join(
                    [gpu_info.get("model") for gpu_info in gpu_names]
                )
            if processor_name := processor.get_name():
                LOGGER.info("Processor: %s", processor_name)
                sys_info_basic["CPU"] = processor_name
            sys_info_mem_storage = {
                "Memory": squire.size_converter(psutil.virtual_memory().total),
                "Disk": squire.size_converter(shutil.disk_usage("/").total),
            }
            if swap := psutil.swap_memory().total:
                sys_info_mem_storage["Swap"] = squire.size_converter(swap)
            sys_info_network = {
                "Private IP address": squire.private_ip_address(),
                "Public IP address": squire.public_ip_address(),
            }
            ctx = dict(
                request=request,
                logout="/logout",
                sys_info_basic=dict(sorted(sys_info_basic.items())),
                sys_info_mem_storage=dict(sorted(sys_info_mem_storage.items())),
                sys_info_network=sys_info_network,
                sys_info_disks=disks.get_all_disks(),
                version=version.__version__,
            )
            return monitor.config.templates.TemplateResponse(
                name="main.html", context=ctx
            )
    else:
        return monitor.config.templates.TemplateResponse(
            name="index.html",
            context={
                "request": request,
                "signin": "/login",
                "version": f"v{version.__version__}",
            },
        )


async def websocket_endpoint(websocket: WebSocket, session_token: str = Cookie(None)):
    """Websocket endpoint to fetch live system resource usage.

    Args:
        websocket: Reference to the websocket object.
        session_token: Session token set after verifying username and password.
    """
    await websocket.accept()
    # Validate session before starting the websocket connection
    try:
        await monitor.authenticator.validate_session(
            websocket.client.host, session_token
        )
    except exceptions.SessionError as error:
        LOGGER.warning(error)
        await websocket.send_text(error.__str__())
        await websocket.close()
        return
    session_timestamp = models.ws_session.client_auth.get(websocket.client.host).get(
        "timestamp"
    )
    # Base task with a placeholder asyncio sleep to start the task loop
    task = asyncio.create_task(asyncio.sleep(0.1))
    # Store disk usage information (during startup) to avoid repeated calls
    disk_info = shutil.disk_usage("/")._asdict()
    while True:
        # Validate session asynchronously (non-blocking)
        # This way of handling session validation is more efficient than using a blocking call
        # This might slip through one iteration even after the session has expired, but it just means one more iteration
        try:
            if task.done():
                await task
                task = asyncio.create_task(
                    monitor.authenticator.validate_session(
                        websocket.client.host, session_token, False
                    )
                )
        except exceptions.SessionError as error:
            LOGGER.warning(error)
            await websocket.send_text(error.__str__())
            await websocket.close()
            return
        except KeyboardInterrupt:
            task.cancel()
            await websocket.send_text("Server Disconnected")
            await websocket.close()
            break
        now = time.time()
        if now - session_timestamp > models.env.monitor_session:
            LOGGER.info("Session expired for %s", websocket.client.host)
            await websocket.send_text("Session Expired")
            await websocket.close()
            break
        data = await resources.system_resources()
        data["disk_info"] = disk_info
        try:
            await websocket.send_json(data)
        except WebSocketDisconnect:
            break
        except KeyboardInterrupt:
            await websocket.send_text("Server Disconnected")
            await websocket.close()
            break
    try:
        if task.done():
            await asyncio.wait_for(task, timeout=1)
        else:
            task.cancel()
    except (
        exceptions.SessionError,
        asyncio.TimeoutError,
        asyncio.CancelledError,
    ) as error:
        LOGGER.warning(error)
