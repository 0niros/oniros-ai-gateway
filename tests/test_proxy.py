import httpx
import respx
from fastapi.testclient import TestClient


@respx.mock
def test_proxies_request_and_injects_upstream_auth(client: TestClient) -> None:
    upstream = respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"id": "chatcmpl-test", "choices": [{"message": {"content": "ok"}}]},
        )
    )

    response = client.post(
        "/deepseek/openai/v1/chat/completions?trace=1",
        headers={
            "Authorization": "Bearer local-dev-key",
            "Content-Type": "application/json",
            "X-Request-ID": "req-1",
        },
        json={"model": "deepseek-chat", "messages": []},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-test"
    assert upstream.called
    request = upstream.calls.last.request
    assert str(request.url) == "https://api.deepseek.com/v1/chat/completions?trace=1"
    assert request.headers["authorization"] == "Bearer deepseek-secret"
    assert request.headers["x-request-id"] == "req-1"


@respx.mock
def test_proxies_anthropic_auth_header(client: TestClient) -> None:
    upstream = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(200, json={"id": "msg_1", "content": []})
    )

    response = client.post(
        "/anthropic/anthropic/v1/messages",
        headers={"Authorization": "Bearer local-dev-key"},
        json={"model": "claude", "messages": []},
    )

    assert response.status_code == 200
    request = upstream.calls.last.request
    assert request.headers["x-api-key"] == "anthropic-secret"
    assert "authorization" not in request.headers


def test_unknown_route_returns_404(client: TestClient) -> None:
    response = client.post(
        "/unknown/openai/v1/chat/completions",
        headers={"Authorization": "Bearer local-dev-key"},
        json={"model": "x"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == (
        "route not found for provider=unknown, protocol=openai"
    )


@respx.mock
def test_missing_upstream_api_key_returns_502(client: TestClient, settings) -> None:
    route = settings.find_route("deepseek", "openai")
    assert route is not None
    route.api_key = None

    response = client.post(
        "/deepseek/openai/v1/chat/completions",
        headers={"Authorization": "Bearer local-dev-key"},
        json={"model": "deepseek-chat", "messages": []},
    )

    assert response.status_code == 502
    assert response.json()["detail"]["error"] == (
        "missing upstream api key for provider=deepseek, protocol=openai"
    )


@respx.mock
def test_upstream_error_body_is_passed_through(client: TestClient) -> None:
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            429,
            headers={"content-type": "application/json"},
            json={"error": {"message": "rate limited"}},
        )
    )

    response = client.post(
        "/deepseek/openai/v1/chat/completions",
        headers={"Authorization": "Bearer local-dev-key"},
        json={"model": "deepseek-chat", "messages": []},
    )

    assert response.status_code == 429
    assert response.json() == {"error": {"message": "rate limited"}}
