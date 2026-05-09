import httpx
import respx
from fastapi.testclient import TestClient


@respx.mock
def test_streaming_response_is_passed_through(client: TestClient) -> None:
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b"data: first\n\ndata: [DONE]\n\n",
        )
    )

    with client.stream(
        "POST",
        "/deepseek/openai/v1/chat/completions",
        headers={"Authorization": "Bearer local-dev-key"},
        json={"model": "deepseek-chat", "stream": True, "messages": []},
    ) as response:
        body = b"".join(response.iter_bytes())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert body == b"data: first\n\ndata: [DONE]\n\n"
