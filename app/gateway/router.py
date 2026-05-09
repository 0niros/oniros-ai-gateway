from __future__ import annotations

from app.config import RouteConfig, Settings
from app.errors import gateway_error


def resolve_route(settings: Settings, provider: str, protocol: str) -> RouteConfig:
    route = settings.find_route(provider, protocol)
    if route is None:
        raise gateway_error(404, f"route not found for provider={provider}, protocol={protocol}")
    return route


def build_upstream_url(route: RouteConfig, upstream_path: str, query_string: str = "") -> str:
    clean_path = upstream_path.lstrip("/")
    url = f"{route.normalized_base_url}/{clean_path}"
    if query_string:
        url = f"{url}?{query_string}"
    return url
