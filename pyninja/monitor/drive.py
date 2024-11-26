import logging

from fastapi.responses import HTMLResponse
from pyninja import monitor

LOGGER = logging.getLogger("uvicorn.default")


async def report() -> HTMLResponse:
    """Generates a disk report using pyudisk.

    Returns:
        HTMLResponse:
        Returns an HTML response with the disk report.
    """
    import pyudisk

    return HTMLResponse(content=pyudisk.generate_report(raw=True))


async def invalid(ctx: str, status_code: int = 500):
    return await monitor.config.clear_session(
        response=HTMLResponse(
            content=ctx, status_code=status_code
        )
    )

