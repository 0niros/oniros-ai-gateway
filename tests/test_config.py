from pathlib import Path

import pytest

from app.config import load_settings


def test_load_settings_from_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
server:
  host: "127.0.0.1"
  port: 9000
gateway_auth:
  enabled: true
  api_keys: ["local-dev-key"]
routes:
  - provider: "DeepSeek"
    protocol: "OpenAI"
    base_url: "https://api.deepseek.com"
    api_key_env: "DEEPSEEK_API_KEY"
    auth:
      header: "Authorization"
      scheme: "Bearer"
http:
  connect_timeout_seconds: 2
  read_timeout_seconds: 10
  max_request_body_mb: 5
""",
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.server.host == "127.0.0.1"
    assert settings.find_route("deepseek", "openai") is not None


def test_rejects_duplicate_routes(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
routes:
  - provider: "deepseek"
    protocol: "openai"
    base_url: "https://api.deepseek.com"
  - provider: "DeepSeek"
    protocol: "OpenAI"
    base_url: "https://api.deepseek.com"
""",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="duplicate route"):
        load_settings(config_path)
