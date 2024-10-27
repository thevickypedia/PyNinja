import logging

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBearer

from pyninja.executors import auth, squire

LOGGER = logging.getLogger("uvicorn.default")
BASIC_AUTH = HTTPBasic()
BEARER_AUTH = HTTPBearer()


async def get_ip_address(
    request: Request,
    public: bool = False,
    apikey: HTTPAuthorizationCredentials = Depends(BEARER_AUTH),
):
    """**Get local and public IP address of the device.**

    **Args:**

        - request: Reference to the FastAPI request object.
        - public: Boolean flag to get the public IP address.
        - apikey: API Key to authenticate the request.

    **Raises:**

        APIResponse:
        Raises the HTTPStatus object with a status code and the public/private IP as response.
    """
    await auth.level_1(request, apikey)
    if public:
        return squire.public_ip_address()
    else:
        return squire.private_ip_address()
