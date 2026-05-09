# Oniros AI Gateway

Oniros AI Gateway is a configurable Python/FastAPI reverse proxy for forwarding
internal AI API traffic to external model providers.

The first version focuses on same-protocol forwarding:

```text
/{provider}/{protocol}/{upstream_path}
```

Examples:

```text
/deepseek/openai/v1/chat/completions
/dashscope/openai/v1/chat/completions
/anthropic/anthropic/v1/messages
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.yaml config.yaml
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Checks

```bash
ruff check .
ruff format --check .
pytest
```
