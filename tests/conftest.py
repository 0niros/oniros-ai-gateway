from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import GatewayAuthConfig, HttpConfig, RouteConfig, Settings, UpstreamAuthConfig


@pytest.fixture
def settings() -> Settings:
    return Settings(
        gateway_auth=GatewayAuthConfig(enabled=True, api_keys=["local-dev-key"]),
        routes=[
            RouteConfig(
                provider="deepseek",
                protocol="openai",
                base_url="https://api.deepseek.com",
                api_key_env="DEEPSEEK_API_KEY",
                auth=UpstreamAuthConfig(header="Authorization", scheme="Bearer"),
            ),
            RouteConfig(
                provider="anthropic",
                protocol="anthropic",
                base_url="https://api.anthropic.com",
                api_key_env="ANTHROPIC_API_KEY",
                auth=UpstreamAuthConfig(header="x-api-key"),
            ),
        ],
        http=HttpConfig(connect_timeout_seconds=1, read_timeout_seconds=5, max_request_body_mb=1),
    )


@pytest.fixture
def client(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")

    from app.main import create_app

    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clear_config_env() -> Iterator[None]:
    original = os.environ.get("ONIROS_CONFIG")
    os.environ.pop("ONIROS_CONFIG", None)
    yield
    if original is not None:
        os.environ["ONIROS_CONFIG"] = original
