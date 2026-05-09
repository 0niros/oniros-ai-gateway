from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request
from starlette.types import Receive, Scope, Send

from app.config import Settings, load_settings
from app.gateway.auth import authenticate_gateway_request
from app.gateway.proxy import proxy_request
from app.gateway.router import resolve_route
from app.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    app_settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        timeout = httpx.Timeout(
            timeout=None,
            connect=app_settings.http.connect_timeout_seconds,
            read=app_settings.http.read_timeout_seconds,
        )
        app.state.http_client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
        yield
        await app.state.http_client.aclose()

    app = FastAPI(title="Oniros AI Gateway", version="0.1.0", lifespan=lifespan)
    app.state.settings = app_settings

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.api_route(
        "/{provider}/{protocol}/{upstream_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    )
    async def gateway(
        request: Request,
        provider: str,
        protocol: str,
        upstream_path: str,
    ) -> Any:
        authenticate_gateway_request(request, app_settings)
        route = resolve_route(app_settings, provider, protocol)
        return await proxy_request(request, route, upstream_path, app.state.http_client)

    return app


class LazyApp:
    def __init__(self) -> None:
        self._app: FastAPI | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._app is None:
            self._app = create_app()
        await self._app(scope, receive, send)


app = LazyApp()
