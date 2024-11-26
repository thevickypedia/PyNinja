import logging

from fastapi.responses import HTMLResponse

LOGGER = logging.getLogger("uvicorn.default")


async def report() -> HTMLResponse:
    """Generates a disk report using pyudisk.

    Returns:
        HTMLResponse:
        Returns an HTML response with the disk report.
    """
    import pyudisk

    return HTMLResponse(content=pyudisk.generate_report(raw=True))
