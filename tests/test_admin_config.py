from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_config_page_loads(client: TestClient) -> None:
    response = client.get("/admin/config")

    assert response.status_code == 200
    assert "Oniros AI Gateway 配置" in response.text


def test_config_raw_requires_gateway_auth(client: TestClient) -> None:
    response = client.get("/admin/config/raw")

    assert response.status_code == 401


def test_config_raw_read_and_save(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
gateway_auth:
  enabled: true
  api_keys:
    - "local-dev-key"
routes:
  - provider: "deepseek"
    protocol: "openai"
    base_url: "https://api.deepseek.com"
    api_key: "old-key"
    auth:
      header: "Authorization"
      scheme: "Bearer"
""",
        encoding="utf-8",
    )

    with TestClient(create_app(config_path=str(config_path))) as client:
        read_response = client.get(
            "/admin/config/raw",
            headers={"Authorization": "Bearer local-dev-key"},
        )
        assert read_response.status_code == 200
        assert "old-key" in read_response.text

        updated = read_response.text.replace("old-key", "new-key")
        save_response = client.post(
            "/admin/config/raw",
            headers={"Authorization": "Bearer local-dev-key"},
            json={"content": updated},
        )
        assert save_response.status_code == 200
        assert save_response.json() == {"status": "saved"}
        assert "new-key" in config_path.read_text(encoding="utf-8")
        assert client.app.state.settings.find_route("deepseek", "openai").api_key == "new-key"


def test_config_save_rejects_invalid_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
gateway_auth:
  enabled: true
  api_keys:
    - "local-dev-key"
routes: []
""",
        encoding="utf-8",
    )

    with TestClient(create_app(config_path=str(config_path))) as client:
        response = client.post(
            "/admin/config/raw",
            headers={"Authorization": "Bearer local-dev-key"},
            json={"content": "routes: ["},
        )

    assert response.status_code == 400
    assert "invalid YAML configuration" in response.json()["detail"]["error"]
