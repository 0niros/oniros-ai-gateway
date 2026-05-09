from __future__ import annotations

from fastapi import Request

from app.config import Settings
from app.errors import gateway_error


def authenticate_gateway_request(request: Request, settings: Settings) -> None:
    if not settings.gateway_auth.enabled:
        return

    authorization = request.headers.get("authorization")
    if not authorization:
        raise gateway_error(401, "missing gateway authorization")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise gateway_error(401, "invalid gateway authorization")

    if token not in settings.gateway_auth.api_keys:
        raise gateway_error(401, "invalid gateway api key")
