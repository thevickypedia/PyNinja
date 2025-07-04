import logging

from fastapi.requests import Request
from fastapi.responses import HTMLResponse

from pyninja import monitor, version
from pyninja.modules import enums, models

LOGGER = logging.getLogger("uvicorn.default")


async def report(request: Request) -> HTMLResponse:
    """Generates a disk report using pyudisk.

    Returns:
        HTMLResponse:
        Returns an HTML response with the disk report.
    """
    import pyudisk

    data = [disk.model_dump() for disk in pyudisk.smart_metrics()]
    if models.OPERATING_SYSTEM == enums.OperatingSystem.linux:
        template = enums.Templates.disk_report_linux
    elif models.OPERATING_SYSTEM == enums.OperatingSystem.darwin:
        template = enums.Templates.disk_report_darwin
    else:
        raise
    return monitor.config.templates.TemplateResponse(
        name=template.value,
        context=dict(
            logout=enums.APIEndpoints.logout,
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
