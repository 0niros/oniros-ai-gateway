#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
CONFIG="${CONFIG:-config.yaml}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
INSTALL_DEV="${INSTALL_DEV:-0}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
UVICORN="$VENV_DIR/bin/uvicorn"

if [ ! -x "$PIP" ]; then
  echo "pip not found in virtual environment: $PIP" >&2
  exit 1
fi

if [ "$INSTALL_DEV" = "1" ]; then
  echo "Installing project with development dependencies"
  "$PIP" install -e ".[dev]"
else
  echo "Installing project runtime dependencies"
  "$PIP" install -e .
fi

if [ ! -f "$CONFIG" ]; then
  if [ ! -f "config.example.yaml" ]; then
    echo "Missing config file and config.example.yaml" >&2
    exit 1
  fi
  echo "Creating $CONFIG from config.example.yaml"
  cp config.example.yaml "$CONFIG"
  echo "Edit $CONFIG and replace placeholder api_key values before calling real providers."
fi

echo "Starting Oniros AI Gateway"
echo "  config: $CONFIG"
echo "  listen: http://$HOST:$PORT"

ONIROS_CONFIG="$CONFIG" exec "$UVICORN" app.main:app --host "$HOST" --port "$PORT"
