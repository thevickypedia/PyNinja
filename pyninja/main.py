import logging
import pathlib

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute

from pyninja import startup, version
from pyninja.executors import routers, squire
from pyninja.modules import enums, exceptions, models, rate_limit

LOGGER = logging.getLogger("uvicorn.default")

PyNinjaAPI = FastAPI(
    title="PyNinja",
    version=version.__version__,
    license_info={"name": "MIT License", "identifier": "MIT"},
)
PyNinjaAPI.__name__ = "PyNinjaAPI"
PyNinjaAPI.routes.append(
    APIRoute(
        path=enums.APIEndpoints.health,
        endpoint=routers.health,
        methods=["GET"],
        include_in_schema=False,
    ),
)


async def docs() -> HTMLResponse:
    """Custom docs endpoint for the Swagger UI.

    See Also:
        The Swagger UI is customized to scroll to the operation when a hyperlink from the description block is selected.

    Returns:
        HTMLResponse:
        Returns an HTMLResponse object with the customized UI.
    """
    html_content = get_swagger_ui_html(
        title=PyNinjaAPI.__dict__.get("title", PyNinjaAPI.__name__),
        openapi_url=PyNinjaAPI.__dict__.get("openapi_url", "/openapi.json"),
        swagger_ui_parameters=models.env.swagger_ui_parameters,
    )
    new_content = html_content.body.decode().replace(
        "</body>", models.fileio.swagger_ui + "</body>"
    )
    return HTMLResponse(new_content)


def start(**kwargs) -> None:
    """Starter function for the API, which uses uvicorn server as trigger.

    Keyword Args:

        Environment_variables_configuration

            - **env_file:** Env filepath to load the environment variables.

        Basic_API_functionalities

            - **apikey:** API Key for authentication.
            - **swagger_ui_parameters:** Parameters for the Swagger UI.
            - **ninja_host:** Hostname for the API server.
            - **ninja_port:** Port number for the API server.

        Functional_improvements

            - **rate_limit:** List of dictionaries with ``max_requests`` and ``seconds`` to apply as rate limit.
            - **log_config:** Logging configuration as a dict or a FilePath. Supports .yaml/.yml, .json or .ini formats.

        Remote_execution_and_FileIO

            - **remote_execution:** Boolean flag to enable remote execution.
            - **api_secret:** Secret access key for running commands on server remotely.
            - **database:** FilePath to store the auth database that handles the authentication errors.

        Monitoring_UI

            - **monitor_username:** Username to authenticate the monitoring page.
            - **monitor_password:** Password to authenticate the monitoring page.
            - **monitor_session:** Session timeout for the monitoring page.
            - **disk_report:** Boolean flag to enable disk report generation.
            - **max_connections:** Maximum number of connections to handle.
            - **no_auth:** Boolean flag to disable authentication for monitoring page.
            - **processes:** List of process names to include in the monitoring page.
            - **services:** List of service names to include in the monitoring page.
            - **service_lib:** Library path to retrieve service info.
            - **smart_lib:** Library path for S.M.A.R.T metrics using PyUdisk.
            - **gpu_lib:** Library path to retrieve GPU names using PyArchitecture.
            - **disk_lib:** Library path to retrieve disk info using PyArchitecture.
            - **processor_lib:** Library path to retrieve processor name using PyArchitecture.
    """
    models.env = squire.load_env(**kwargs)
    models.architecture = squire.load_architecture(models.env)
    squire.assert_tokens()
    squire.assert_pyudisk()
    squire.handle_warnings()
    startup.docs_handler(api=PyNinjaAPI, func=docs)
    dependencies = [
        Depends(dependency=rate_limit.RateLimiter(each_rate_limit).init)
        for each_rate_limit in models.env.rate_limit
    ]
    get_routes = models.RoutingHandler(
        type=enums.APIRouteType.get, routes=routers.get_api(dependencies)
    )
    post_routes = models.RoutingHandler(
        type=enums.APIRouteType.post, routes=routers.post_api(dependencies)
    )
    monitor_routes = models.RoutingHandler(
        type=enums.APIRouteType.monitor, routes=routers.monitoring_ui(dependencies)
    )

    # Conditional endpoints based on 'apikey' value
    if models.env.apikey:
        # Redirect to docs page if apikey is set
        PyNinjaAPI.routes.append(
            APIRoute(
                path=enums.APIEndpoints.root,
                endpoint=routers.docs_redirect,
                methods=["GET"],
                include_in_schema=False,
            ),
        )
        PyNinjaAPI.routes.extend(get_routes.routes)
        get_routes.enabled = True

    # Conditional endpoints based on 'remote_execution' and 'api_secret' values
    if all((models.env.apikey, models.env.api_secret, models.env.remote_execution)):
        models.database = models.Database(models.env.database)
        models.database.create_table("auth_errors", ["host", "block_until"])
        PyNinjaAPI.routes.extend(post_routes.routes)
        post_routes.enabled = True

    # Conditional endpoints based on 'monitor_username' and 'monitor_password' values
    if all((models.env.monitor_username, models.env.monitor_password)):
        PyNinjaAPI.routes.extend(monitor_routes.routes)
        monitor_routes.enabled = True
        PyNinjaAPI.add_exception_handler(
            exc_class_or_status_code=exceptions.RedirectException,
            handler=startup.redirect_exception_handler,  # noqa: PyTypeChecker
        )
        if not models.env.apikey:
            # Redirect to /monitor page if apikey is not set
            PyNinjaAPI.routes.append(
                APIRoute(
                    path=enums.APIEndpoints.root,
                    endpoint=routers.monitor_redirect,
                    methods=["GET"],
                    include_in_schema=False,
                ),
            )

    PyNinjaAPI.description = startup.get_desc(get_routes, post_routes, monitor_routes)
    module_name = pathlib.Path(__file__)
    kwargs = dict(
        host=models.env.ninja_host,
        port=models.env.ninja_port,
        app=f"{module_name.parent.stem}.{module_name.stem}:{PyNinjaAPI.__name__}",
    )
    if models.env.log_config:
        kwargs["log_config"] = models.env.log_config
    uvicorn.run(**kwargs)
