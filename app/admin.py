from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel
from starlette.responses import HTMLResponse, PlainTextResponse

from app.config import Settings, parse_settings_yaml
from app.errors import gateway_error
from app.gateway.auth import authenticate_gateway_request


class ConfigUpdate(BaseModel):
    content: str


ADMIN_CONFIG_PAGE = Path(__file__).resolve().parent / "web" / "admin_config.html"


def build_admin_router(config_path: Path | None) -> APIRouter:
    router = APIRouter(prefix="/admin", tags=["admin"])

    @router.get("/config", response_class=HTMLResponse)
    async def config_page() -> str:
        return ADMIN_CONFIG_PAGE.read_text(encoding="utf-8")

    @router.get("/config/raw", response_class=PlainTextResponse)
    async def read_config(request: Request) -> str:
        settings = _current_settings(request)
        authenticate_gateway_request(request, settings)
        path = _require_config_path(config_path)
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise gateway_error(404, f"configuration file not found: {path}") from exc

    @router.post("/config/raw")
    async def save_config(request: Request, update: ConfigUpdate) -> dict[str, str]:
        settings = _current_settings(request)
        authenticate_gateway_request(request, settings)
        path = _require_config_path(config_path)
        new_settings = _parse_update(update.content)
        path.write_text(update.content, encoding="utf-8")
        request.app.state.settings = new_settings
        await _replace_http_client(request, new_settings)
        return {"status": "saved"}

    return router


def _current_settings(request: Request) -> Settings:
    return request.app.state.settings


def _require_config_path(config_path: Path | None) -> Path:
    if config_path is None:
        raise gateway_error(409, "configuration file editing is unavailable for this app instance")
    return config_path


def _parse_update(content: str) -> Settings:
    try:
        return parse_settings_yaml(content)
    except RuntimeError as exc:
        raise gateway_error(400, str(exc)) from exc


async def _replace_http_client(request: Request, settings: Settings) -> None:
    old_client: httpx.AsyncClient = request.app.state.http_client
    request.app.state.http_client = build_http_client(settings)
    await old_client.aclose()


def build_http_client(settings: Settings) -> httpx.AsyncClient:
    timeout = httpx.Timeout(
        timeout=None,
        connect=settings.http.connect_timeout_seconds,
        read=settings.http.read_timeout_seconds,
    )
    return httpx.AsyncClient(timeout=timeout, follow_redirects=False)
