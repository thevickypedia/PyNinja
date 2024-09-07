import asyncio
import logging
import time
from http import HTTPStatus

from fastapi import Cookie, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from .. import exceptions, models, monitor, squire, version

LOGGER = logging.getLogger("uvicorn.default")


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
                "signin": monitor.config.static.login_endpoint,
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
                "detail": "Session Expired",
                "signin": monitor.config.static.login_endpoint,
                "show_login": True,
                "version": f"v{version.__version__}",
            },
        )
    return await monitor.config.clear_session(response)


async def login_endpoint(
    request: Request, authorization: str = Header(None)
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
        content={"redirect_url": monitor.config.static.monitor_endpoint},
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
            return monitor.config.templates.TemplateResponse(
                name="main.html",
                context=dict(
                    request=request,
                    default_cpu_interval=models.ws_settings.cpu_interval,
                    default_refresh_interval=models.ws_settings.refresh_interval,
                ),
            )
    else:
        return monitor.config.templates.TemplateResponse(
            name="index.html",
            context={
                "request": request,
                "signin": monitor.config.static.login_endpoint,
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
    try:
        session_validity = await monitor.authenticator.validate_session(
            websocket.client.host, session_token
        )
    except exceptions.SessionError as error:
        await websocket.send_text(error.__str__())
        await websocket.close()
        return
    if not session_validity:
        await websocket.send_text("Unauthorized")
        await websocket.close()
        return
    session_timestamp = models.ws_session.client_auth.get(websocket.client.host).get(
        "timestamp"
    )
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
