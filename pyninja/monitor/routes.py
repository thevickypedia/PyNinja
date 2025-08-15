import asyncio
import logging
import time
from http import HTTPStatus

from fastapi import Cookie, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.websockets import WebSocket, WebSocketDisconnect

from pyninja import monitor, version
from pyninja.modules import enums, exceptions, models

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
        request,
        monitor.config.templates.TemplateResponse(
            name=enums.Templates.unauthorized.value,
            context={
                "request": request,
                "signin": enums.APIEndpoints.login,
                "version": f"v{version.__version__}",
            },
        ),
    )


async def logout_endpoint(request: Request) -> HTMLResponse:
    """Logs out the user and clears the session token.

    Args:
        request: Reference to the FastAPI request object.

    Returns:
        HTMLResponse:
        Redirects to login page.
    """
    session_token = request.cookies.get(enums.Cookies.session_token)
    try:
        await monitor.authenticator.validate_session(request.client.host, session_token)
    except exceptions.SessionError as error:
        response = await monitor.authenticator.session_error(request, error)
    else:
        models.ws_session.client_auth.pop(request.client.host, None)
        response = monitor.config.templates.TemplateResponse(
            name=enums.Templates.logout.value,
            context={
                "request": request,
                "signin": enums.APIEndpoints.login,
                "detail": "You have been logged out successfully.",
                "show_login": False,
                "version": f"v{version.__version__}",
            },
        )
    return await monitor.config.clear_session(request, response)


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
        content={"redirect_url": enums.APIEndpoints.monitor},
        status_code=HTTPStatus.OK,
    )
    response.set_cookie(**await monitor.authenticator.generate_cookie(auth_payload))
    response.set_cookie(
        key="render",
        value=request.headers.get("Content-Type"),
        expires=await monitor.config.get_expiry(
            lease_start=int(time.time()), lease_duration=models.env.monitor_session
        ),
    )
    return response


async def monitor_endpoint(
    request: Request, session_token: str = Cookie(None), render: str = Cookie(None)
):
    """Renders the UI for monitoring page.

    Args:
        request: Reference to the FastAPI request object.
        session_token: Session token set after verifying username and password.
        render: Render option set by the UI.

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
    if session_token or models.env.no_auth:
        if not models.env.no_auth:
            try:
                await monitor.authenticator.validate_session(
                    request.client.host, session_token
                )
            except exceptions.SessionError as error:
                LOGGER.error("Session token mismatch: %s", error)
                return await monitor.config.clear_session(
                    request, await monitor.authenticator.session_error(request, error)
                )
        # If disk_report was not enabled on the server, the Content-Type header or Cookie for render is not honored
        if not models.env.disk_report:
            render = enums.Cookies.monitor
        if not render:
            # no_auth mode supports render option via query params
            # Example: http://0.0.0.0:8080/monitor?render=drive
            if qparam := request.query_params.get("render"):
                LOGGER.info("Render value received via query params - '%s'", qparam)
                render = qparam
        if render == enums.Cookies.monitor:
            ctx = monitor.resources.landing_page()
            ctx["request"] = request
            ctx["version"] = version.__version__
            LOGGER.info("Rendering initial context for monitoring page!")
            return monitor.config.templates.TemplateResponse(
                name=enums.Templates.main.value, context=ctx
            )
        elif render == enums.Cookies.drive:
            LOGGER.info("Rendering disk report!")
            try:
                return await monitor.drive.report(request)
            except Exception as error:
                LOGGER.error(error)
                return await monitor.drive.invalidate("Failed to generate disk report")
    return monitor.config.templates.TemplateResponse(
        name=enums.Templates.index.value,
        context={
            "request": request,
            "signin": enums.APIEndpoints.login,
            "version": f"v{version.__version__}",
            "disk_report": models.env.disk_report,
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
    if models.env.no_auth:
        session_timestamp = time.time()
    else:
        session_timestamp = models.ws_session.client_auth.get(
            websocket.client.host
        ).get("timestamp")
    # Base task with a placeholder asyncio sleep to start the task loop
    task = asyncio.create_task(asyncio.sleep(0.1))
    connections = 0
    while True:
        # Validate session asynchronously (non-blocking)
        # This way of handling session validation is more efficient than using a blocking call
        # This might slip through one iteration even after the session has expired, but it just means <1s delay
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
        data = await monitor.resources.system_resources()
        try:
            await websocket.send_json(data)
            connections += 1
        except WebSocketDisconnect:
            break
        except KeyboardInterrupt:
            await websocket.send_text("Server Disconnected")
            await websocket.close()
            break
    LOGGER.info("WS connections made: %s", connections)
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
