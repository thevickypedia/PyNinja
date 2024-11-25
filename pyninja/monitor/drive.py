import os

from fastapi.responses import HTMLResponse


def report():
    """Generated disk utility report and returns an HTMLResponse."""
    try:
        import pyudisk

        report_file = os.path.join(os.getcwd(), "disk-report.html")
        return HTMLResponse(
            content=pyudisk.generate_report(filepath=report_file, raw=True)
        )
    except Exception:
        return None
