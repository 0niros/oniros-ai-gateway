from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, HttpUrl, ValidationError, field_validator, model_validator


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class GatewayAuthConfig(BaseModel):
    enabled: bool = True
    api_keys: list[str] = Field(default_factory=list)


class UpstreamAuthConfig(BaseModel):
    header: str
    scheme: str | None = None


class RouteConfig(BaseModel):
    provider: str
    protocol: str
    base_url: HttpUrl
    api_key: str | None = None
    auth: UpstreamAuthConfig | None = None

    @field_validator("provider", "protocol")
    @classmethod
    def normalize_route_part(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("route part cannot be empty")
        if "/" in value:
            raise ValueError("route part cannot contain '/'")
        return value

    @property
    def route_key(self) -> tuple[str, str]:
        return self.provider, self.protocol

    @property
    def normalized_base_url(self) -> str:
        return str(self.base_url).rstrip("/")


class HttpConfig(BaseModel):
    connect_timeout_seconds: float = 10
    read_timeout_seconds: float = 300
    max_request_body_mb: int = 20


class Settings(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    gateway_auth: GatewayAuthConfig = Field(default_factory=GatewayAuthConfig)
    routes: list[RouteConfig] = Field(default_factory=list)
    http: HttpConfig = Field(default_factory=HttpConfig)

    @model_validator(mode="after")
    def validate_routes(self) -> Settings:
        seen: set[tuple[str, str]] = set()
        for route in self.routes:
            if route.route_key in seen:
                provider, protocol = route.route_key
                raise ValueError(f"duplicate route for provider={provider}, protocol={protocol}")
            seen.add(route.route_key)
        return self

    def find_route(self, provider: str, protocol: str) -> RouteConfig | None:
        normalized = (provider.lower(), protocol.lower())
        for route in self.routes:
            if route.route_key == normalized:
                return route
        return None


def load_settings(path: str | Path | None = None) -> Settings:
    config_path = resolve_config_path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise RuntimeError(f"configuration file not found: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise RuntimeError(f"invalid YAML configuration: {config_path}") from exc

    try:
        return Settings.model_validate(raw)
    except ValidationError as exc:
        raise RuntimeError(f"invalid configuration: {exc}") from exc


def resolve_config_path(path: str | Path | None = None) -> Path:
    return Path(path or os.getenv("ONIROS_CONFIG", "config.yaml"))


def parse_settings_yaml(content: str) -> Settings:
    try:
        raw = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"invalid YAML configuration: {exc}") from exc

    try:
        return Settings.model_validate(raw)
    except ValidationError as exc:
        raise RuntimeError(f"invalid configuration: {exc}") from exc
