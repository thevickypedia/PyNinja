import logging
import subprocess
from collections.abc import Generator
from http import HTTPStatus

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


def parse_certificate_output(
    output: str, raw: bool, include_path: bool
) -> Generator[models.Certificate]:
    """Parse the output from the certbot command to extract certificate details.

    Args:
        output: The output string from the certbot command.

    Yields:
        models.Certificate:
        A generator yielding Certificate objects with parsed details.
    """
    lines = output.strip().split("\n")
    for line in lines:
        if line.startswith("Certificate Name:"):
            cert_info = {
                "Certificate Name" if raw else "certificate_name": line.split(": ")[
                    1
                ].strip()
            }
        elif line.startswith("Serial Number:"):
            cert_info["Serial Number" if raw else "serial_number"] = line.split(": ")[
                1
            ].strip()
        elif line.startswith("Key Type:"):
            cert_info["Key Type" if raw else "key_type"] = line.split(": ")[1].strip()
        elif line.startswith("Domains:"):
            cert_info["Domains" if raw else "domains"] = (
                line.split(": ")[1].strip().split()
            )
        elif line.startswith("Expiry Date:"):
            expiry_date = (
                line.split(": ")[1].strip().split("VALID")[0].replace("(", "").strip()
            )
            validity = line.split("VALID:")[1].strip().replace(")", "")
            cert_info["Expiry Date" if raw else "expiry_date"] = expiry_date
            cert_info["Validity" if raw else "valid_days"] = (
                validity if raw else int(validity.split()[0])
            )
        elif line.startswith("Certificate Path:"):
            if include_path:
                cert_info["Certificate Path" if raw else "certificate_path"] = (
                    line.split(": ")[1].strip()
                )
        elif line.startswith("Private Key Path:"):
            if include_path:
                cert_info["Private Key Path" if raw else "private_key_path"] = (
                    line.split(": ")[1].strip()
                )
            yield cert_info if raw else models.Certificate(**cert_info)


@cache.timed_cache(max_age=300)
def get_all_certificates(
    raw: bool = False, include_path: bool = True
) -> models.CertificateStatus:
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
        if all_certificates := list(
            parse_certificate_output(output, raw, include_path)
        ):
            print(len(all_certificates), "certificates found.")
            return models.CertificateStatus(
                status_code=HTTPStatus.OK.real,
                description="Successfully fetched all certificates.",
                certificates=all_certificates,
            )
    except subprocess.CalledProcessError as error:
        return models.CertificateStatus(
            status_code=HTTPStatus.EXPECTATION_FAILED.real,
            description=squire.log_subprocess_error(error),
        )
