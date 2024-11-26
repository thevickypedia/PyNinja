import logging

from fastapi.requests import Request
from fastapi.responses import HTMLResponse

from pyninja import monitor, version
from pyninja.modules import enums

LOGGER = logging.getLogger("uvicorn.default")


async def report(request: Request) -> HTMLResponse:
    """Generates a disk report using pyudisk.

    Returns:
        HTMLResponse:
        Returns an HTML response with the disk report.
    """
    from pyudisk.config import EnvConfig
    from pyudisk.main import monitor_disk

    data = [disk.model_dump() for disk in monitor_disk(EnvConfig())]
    return monitor.config.templates.TemplateResponse(
        name=enums.Templates.disk_report.value,
        context=dict(
            logout="/logout",
            request=request,
            data=data,
            version=f"v{version.__version__}",
        ),
    )


async def invalidate(ctx: str, status_code: int = 500) -> HTMLResponse:
    """Invalidates the cache after wrapping the context into HTMLResponse object.

    Args:
        ctx: Content to enter into the HTMLResponse object.
        status_code: Status code for the response.

    Returns:
        HTMLResponse:
        Returns an HTML response with the given context and status code.
    """
    response = HTMLResponse(content=ctx, status_code=status_code)
    response.delete_cookie(key="render")
    return response
