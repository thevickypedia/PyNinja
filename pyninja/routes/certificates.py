"""Module to handle certificates API endpoint."""

import logging
from http import HTTPStatus
from typing import Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pyninja.executors import auth
from pyninja.features import certificates
from pyninja.modules import exceptions

LOGGER = logging.getLogger("uvicorn.default")
BEARER_AUTH = HTTPBearer()


async def get_certificate(
    request: Request,
    name: Optional[str] = "all",
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """API handler to get certificates.

    Args:
        - request: Reference to the FastAPI request object.
        - name: Name of the certificate to retrieve.
        - raw: If True, returns raw certificate data instead of parsed model.
        - apikey: API Key to authenticate the request.
    """
    await auth.level_1(request, apikey)
    cert_response = await certificates.get_all_certificates(raw=True, ws_stream=False)
    if cert_response.status_code == HTTPStatus.OK:
        if name and name != "all":
            for cert in cert_response.certificates:
                if cert["Certificate Name"] == name:
                    raise exceptions.APIResponse(
                        status_code=HTTPStatus.OK,
                        detail=cert,
                    )
            raise exceptions.APIResponse(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"Certificate '{name}' not found.",
            )
        raise exceptions.APIResponse(
            status_code=cert_response.status_code,
            detail=cert_response.certificates,
        )
    raise exceptions.APIResponse(
        status_code=cert_response.status_code,
        detail=cert_response.description,
    )
