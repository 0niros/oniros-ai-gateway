from fastapi.testclient import TestClient


def test_requires_gateway_authorization(client: TestClient) -> None:
    response = client.post("/deepseek/openai/v1/chat/completions", json={"model": "x"})

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "missing gateway authorization"


def test_rejects_invalid_gateway_authorization(client: TestClient) -> None:
    response = client.post(
        "/deepseek/openai/v1/chat/completions",
        headers={"Authorization": "Bearer wrong"},
        json={"model": "x"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "invalid gateway api key"
