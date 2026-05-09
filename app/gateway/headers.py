from __future__ import annotations

import os
from collections.abc import Mapping

from app.config import RouteConfig
from app.errors import gateway_error

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

REQUEST_ONLY_HEADERS = {
    "host",
    "content-length",
    "authorization",
}

RESPONSE_ONLY_HEADERS = {
    "content-length",
}


def build_upstream_headers(headers: Mapping[str, str], route: RouteConfig) -> dict[str, str]:
    blocked = HOP_BY_HOP_HEADERS | REQUEST_ONLY_HEADERS
    if route.auth is not None:
        blocked.add(route.auth.header.lower())

    upstream_headers = {
        name: value for name, value in headers.items() if name.lower() not in blocked
    }

    if route.auth is not None and route.api_key_env:
        api_key = os.getenv(route.api_key_env)
        if not api_key:
            raise gateway_error(502, f"missing upstream api key env: {route.api_key_env}")
        upstream_headers[route.auth.header] = _format_auth_value(api_key, route.auth.scheme)

    return upstream_headers


def build_downstream_headers(headers: Mapping[str, str]) -> dict[str, str]:
    blocked = HOP_BY_HOP_HEADERS | RESPONSE_ONLY_HEADERS
    return {name: value for name, value in headers.items() if name.lower() not in blocked}


def _format_auth_value(api_key: str, scheme: str | None) -> str:
    if not scheme:
        return api_key
    return f"{scheme} {api_key}"
