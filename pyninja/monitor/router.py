import asyncio
import logging
import time
from http import HTTPStatus

from fastapi import Request, Cookie
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from pyninja import (
    models,
    squire,
    monitor
)

LOGGER = logging.getLogger("uvicorn.default")


async def error_endpoint(request: Request) -> HTMLResponse:
    """Renders the error page.

    Args:
        request: Reference to the FastAPI request object.

    Returns:
        HTMLResponse:
        Returns an HTML response templated using Jinja2.
    """
    print(request.headers)
    print(request.cookies)
    return monitor.templates.TemplateResponse(
        name="unauthorized.html",
        context={"request": request, "signin": monitor.config.static.login_endpoint},
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
    if session_token:
        await monitor.authenticator.validate_session(request.client.host, session_token)
        models.ws_session.client_auth.pop(request.client.host)
        response = monitor.templates.TemplateResponse(
            name="logout.html",
            context={"request": request, "detail": "Session Expired", "signin": monitor.config.static.login_endpoint,
                     "show_login": True}
        )
    else:
        response = monitor.templates.TemplateResponse(
            name="session.html",
            context={"request": request, "signin": monitor.config.static.login_endpoint, "reason": "Session Expired"},
        )
    response.delete_cookie("session_token")
    return response


async def login_endpoint(request: Request) -> JSONResponse:
    """Reads the root request to render HTMl page.

    Returns:
        JSONResponse:
        Redirects to login page.
    """
    auth_payload = await monitor.authenticator.verify_login(request)
    # AJAX calls follow redirect and return the response instead of replacing the URL
    # Solution is to revert to Form, but that won't allow header auth and additional customization done by JavaScript
    response = JSONResponse(content={"redirect_url": monitor.config.static.monitor_endpoint}, status_code=HTTPStatus.OK)
    response.set_cookie(**await monitor.authenticator.generate_cookie(auth_payload))
    return response


async def monitor_endpoint(request: Request,
                           session_token: str = Cookie(None)):
    """Renders the UI for monitoring page.

    Args:
        request: Reference to the FastAPI request object.
        session_token: Session token set after verifying username and password.

    Returns:
        HTMLResponse:
        Returns an HTML response templated using Jinja2.
    """
    if not session_token:
        return monitor.templates.TemplateResponse(
            name="index.html",
            context={"request": request, "signin": monitor.config.static.login_endpoint}
        )
    await monitor.authenticator.validate_session(request.client.host, session_token)
    return monitor.templates.TemplateResponse(
        name="main.html",
        context=dict(
            request=request,
            default_cpu_interval=models.ws_settings.cpu_interval,
            default_refresh_interval=models.ws_settings.refresh_interval,
        )
    )


async def websocket_endpoint(websocket: WebSocket):
    """Websocket endpoint to fetch live system resource usage.

    Args:
        websocket: Reference to the websocket object.
    """
    await websocket.accept()
    session_token = websocket.cookies.get("session_token") or websocket.headers.get(
        "cookie", {}
    ).get("session_token")
    if not monitor.authenticator.validate_session(websocket.client.host, session_token):
        await websocket.send_text("Unauthorized")
        await websocket.close()
        return
    session_timestamp = models.ws_session.client_auth.get(websocket.client.host).get("timestamp")
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
        if now - session_timestamp > models.env.monitor_session:
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
