from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from starlette.types import Receive, Scope, Send

from app.admin import build_admin_router, build_http_client
from app.config import Settings, load_settings, resolve_config_path
from app.gateway.auth import authenticate_gateway_request
from app.gateway.proxy import proxy_request
from app.gateway.router import resolve_route
from app.logging import configure_logging


def create_app(settings: Settings | None = None, config_path: str | None = None) -> FastAPI:
    configure_logging()
    actual_config_path = None if settings is not None else resolve_config_path(config_path)
    app_settings = settings or load_settings(actual_config_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.http_client = build_http_client(app.state.settings)
        yield
        await app.state.http_client.aclose()

    app = FastAPI(title="Oniros AI Gateway", version="0.1.0", lifespan=lifespan)
    app.state.settings = app_settings
    app.include_router(build_admin_router(actual_config_path))

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
        current_settings = request.app.state.settings
        authenticate_gateway_request(request, current_settings)
        route = resolve_route(current_settings, provider, protocol)
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
