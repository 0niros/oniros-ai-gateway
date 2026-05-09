from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx
from fastapi import Request
from starlette.responses import StreamingResponse

from app.config import RouteConfig
from app.errors import gateway_error
from app.gateway.headers import build_downstream_headers, build_upstream_headers
from app.gateway.router import build_upstream_url

logger = logging.getLogger(__name__)


async def proxy_request(
    request: Request,
    route: RouteConfig,
    upstream_path: str,
    client: httpx.AsyncClient,
) -> StreamingResponse:
    body = await request.body()
    upstream_url = build_upstream_url(route, upstream_path, request.url.query)
    upstream_headers = build_upstream_headers(request.headers, route)

    try:
        upstream_request = client.build_request(
            request.method,
            upstream_url,
            headers=upstream_headers,
            content=body,
        )
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.TimeoutException as exc:
        logger.warning("upstream timeout provider=%s protocol=%s", route.provider, route.protocol)
        raise gateway_error(504, "upstream timeout") from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "upstream request failed provider=%s protocol=%s error=%s",
            route.provider,
            route.protocol,
            exc,
        )
        raise gateway_error(502, "upstream request failed") from exc

    downstream_headers = build_downstream_headers(upstream_response.headers)

    return StreamingResponse(
        _stream_upstream_response(upstream_response),
        status_code=upstream_response.status_code,
        headers=downstream_headers,
        media_type=upstream_response.headers.get("content-type"),
    )


async def _stream_upstream_response(response: httpx.Response) -> AsyncIterator[bytes]:
    try:
        async for chunk in response.aiter_raw():
            if chunk:
                yield chunk
    finally:
        await response.aclose()
