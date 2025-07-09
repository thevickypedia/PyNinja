import logging
import sys
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.routing import APIRoute, APIWebSocketRoute

from pyninja.modules import enums, exceptions, models

LOGGER = logging.getLogger("uvicorn.default")


def docs_handler(api: FastAPI, func: Callable) -> None:
    """Removes the default Swagger UI endpoint and adds a custom ``docs`` endpoint.

    Args:
        api: FastAPI object to modify the routes.
        func: Callable function to be used as the endpoint for the custom docs.

    References:
        https://swagger.io/docs/open-source-tools/swagger-ui/usage/configuration/
    """
    for __route in api.routes:
        if __route.__dict__.get("name", "") == "swagger_ui_html":
            api.routes.remove(__route)
    api.routes.append(
        APIRoute(
            path=enums.APIEndpoints.docs,
            endpoint=func,
            methods=["GET", "POST", "DELETE"],
            include_in_schema=False,
        ),
    )


def generate_hyperlink(route: APIRoute | APIWebSocketRoute) -> str:
    """Generates hyperlink for a particular API route to be included in the description.

    Args:
        route: APIRoute or APIWebSocketRoute object.

    Returns:
        str:
        Returns the hyperlink as a string.
    """
    method = list(route.methods)[0].lower()
    route_path = route.path.lstrip("/").replace("-", "_")
    return f"\n- <a href='#/default/{route.name}_{route_path}_{method}'>{route.path}</a><br>"


def get_desc(
    get_routes: models.RoutingHandler,
    post_routes: models.RoutingHandler,
    monitor_routes: models.RoutingHandler,
) -> str:
    """Construct a detailed description for the API docs.

    Args:
        get_routes: RoutingHandler object for GET endpoints.
        post_routes: RoutingHandler object for POST endpoints.
        monitor_routes: RoutingHandler object for MONITOR endpoints.

    Returns:
        str:
        Returns the description as a string.
    """
    basic_fl, remote_fl, monitor_fl = ("Disabled",) * 3
    if get_routes.enabled:
        basic_fl = "All basic GET calls have been enabled"
    if post_routes.enabled:
        n = enums.APIEndpoints.run_command.name
        v = enums.APIEndpoints.run_command.value
        remote_fl = f"Enabled at <a href='#/default/{n}_{n}_post'>{v}</a>"
    monitor_ui = enums.APIEndpoints.monitor.value
    if monitor_routes.enabled:
        monitor_fl = f"Enabled at <a href='{monitor_ui}'>{monitor_ui}</a>"
    description = "**Lightweight OS-agnostic service monitoring API**"
    description += (
        "\n\nIn addition to monitoring services, processes, and containers,"
        "the PyNinja API provides optional features for executing remote commands "
        "and hosting a real-time system resource monitoring page. 🚀"
    )
    description += f"\n\n**Python version:** {sys.version.split()[0]} - {sys.version_info.releaselevel}"
    description += "\n\n#### Basic Features"
    for route in get_routes.routes:
        description += generate_hyperlink(route)
    description += "\n\n#### Additional Features**"
    for route in post_routes.routes:
        description += generate_hyperlink(route)
    description += f"\n- <a href='{monitor_ui}'>{monitor_ui}</a><br>"
    description += (
        "\n> **Additional features are available based on server configuration."
    )
    description += "\n\n#### Current State"
    description += f"\n- **Basic Execution:** {basic_fl}"
    description += f"\n- **Remote Execution:** {remote_fl}"
    description += f"\n- **Monitoring Page:** {monitor_fl}"
    description += "\n\n#### Links"
    description += "\n- <a href='https://pypi.org/project/PyNinja/'>PyPi</a><br>"
    description += (
        "\n- <a href='https://github.com/thevickypedia/PyNinja'>GitHub</a><br>"
    )
    description += (
        "\n- <a href='https://thevickypedia.github.io/PyNinja/'>Runbook</a><br>"
    )
    return description


async def redirect_exception_handler(
    request: Request, exception: exceptions.RedirectException
) -> JSONResponse:
    """Custom exception handler to handle redirect.

    Args:
        request: Takes the ``Request`` object as an argument.
        exception: Takes the ``RedirectException`` object inherited from ``Exception`` as an argument.

    Returns:
        JSONResponse:
        Returns the JSONResponse with content, status code and cookie.
    """
    LOGGER.debug("Exception headers: %s", request.headers)
    LOGGER.debug("Exception cookies: %s", request.cookies)
    if request.url.path == enums.APIEndpoints.login:
        response = JSONResponse(
            content={"redirect_url": exception.location}, status_code=200
        )
    else:
        response = RedirectResponse(url=exception.location)
    if exception.detail:
        response.set_cookie(
            "detail", exception.detail.upper(), httponly=True, samesite="strict"
        )
    return response
