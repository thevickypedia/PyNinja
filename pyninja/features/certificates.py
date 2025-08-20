import logging
import subprocess
from collections.abc import Generator
from http import HTTPStatus
from typing import Any, Dict

from pyninja.executors import squire
from pyninja.modules import cache, enums, models

LOGGER = logging.getLogger("uvicorn.default")


def forbidden() -> models.CertificateStatus:
    """Return a forbidden response when host password is not stored.

    Returns:
        models.CertificateStatus:
        A CertificateStatus object indicating that the host password is not stored.
    """
    return models.CertificateStatus(
        status_code=HTTPStatus.FORBIDDEN.real,
        description="'host_password' not stored, certificates cannot be accessed.",
    )


def parse_certificate_output(output: str, raw: bool, ws_stream: bool) -> Generator[Dict[str, Any]]:
    """Parse the output from the certbot command to extract certificate details.

    Args:
        output: The output string from the certbot command.
        raw: If True, returns raw certificate data instead of parsed model.
        ws_stream: If True, omits file paths and serial numbers for simplicity.

    Yields:
        Dict[str, Any]:
        A generator yielding Certificate objects with parsed details.
    """
    cert_key = lambda k: k if raw else k.lower().replace(" ", "_")  # noqa: E731
    lines = output.strip().split("\n")
    for line in lines:
        cert_info = {}
        if line.startswith("Certificate Name:"):
            cert_info[cert_key("Certificate Name")] = line.split(": ")[1].strip()
        elif line.startswith("Serial Number:"):
            if not ws_stream:
                cert_info[cert_key("Serial Number")] = line.split(": ")[1].strip()
        elif line.startswith("Key Type:"):
            cert_info[cert_key("Key Type")] = line.split(": ")[1].strip()
        elif line.startswith("Domains:"):
            cert_info[cert_key("Domains")] = line.split(": ")[1].strip().split()
        elif line.startswith("Expiry Date:"):
            expiry_date = line.split(": ")[1].strip().split("VALID")[0].replace("(", "").strip()
            validity = line.split("VALID:")[1].strip().replace(")", "")
            cert_info[cert_key("Expiry Date")] = expiry_date
            cert_info[cert_key("Validity")] = validity if raw else int(validity.split()[0])
        elif line.startswith("Certificate Path:"):
            if not ws_stream:
                cert_info[cert_key("Certificate Path")] = line.split(": ")[1].strip()
        elif line.startswith("Private Key Path:"):
            if not ws_stream:
                cert_info[cert_key("Private Key Path")] = line.split(": ")[1].strip()
            yield cert_info


@cache.timed_cache(max_age=1_800)
async def get_all_certificates(raw: bool = False, ws_stream: bool = False) -> models.CertificateStatus:
    """Fetch all SSL certificates using certbot.

    Returns:
        models.CertificateStatus:
        A CertificateStatus object containing the status code and a list of certificates.
    """
    if models.OPERATING_SYSTEM == enums.OperatingSystem.windows:
        return models.CertificateStatus(
            status_code=HTTPStatus.FORBIDDEN.real,
            description="Host is running Windows, cannot access certificates.",
        )
    if not models.env.host_password:
        return forbidden()
    if not models.env.certbot_path:
        return models.CertificateStatus(
            status_code=HTTPStatus.EXPECTATION_FAILED.real,
            description="'certbot' not installed.",
        )
    try:
        output = subprocess.check_output(
            f"echo {models.env.host_password} | sudo -S {models.env.certbot_path} certificates",
            shell=True,
            text=True,
        )
        if not output.strip() or "No certificates found" in output:
            return models.CertificateStatus(
                status_code=HTTPStatus.NO_CONTENT.real,
                description="No certificates found.",
            )
        if all_certificates := list(parse_certificate_output(output, raw, ws_stream)):
            LOGGER.info("Successfully parsed %d certificates.", len(all_certificates))
            return models.CertificateStatus(
                status_code=HTTPStatus.OK.real,
                description="Successfully parsed all certificates.",
                certificates=all_certificates,
            )
        else:
            return models.CertificateStatus(
                status_code=HTTPStatus.PARTIAL_CONTENT.real,
                description="Failed to parse some certificates.",
                certificates=output.strip().split("\n"),
            )
    except subprocess.CalledProcessError as error:
        return models.CertificateStatus(
            status_code=HTTPStatus.EXPECTATION_FAILED.real,
            description=squire.log_subprocess_error(error),
        )
