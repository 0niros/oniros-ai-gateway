#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
CONFIG="${CONFIG:-config.yaml}"
INSTALL_DEV="${INSTALL_DEV:-0}"
FOREGROUND="${FOREGROUND:-0}"
LOG_DIR="${LOG_DIR:-logs}"
PID_FILE="${PID_FILE:-$LOG_DIR/gateway.pid}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/gateway.log}"

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

CONFIG_HOST="$("$VENV_DIR/bin/python" -c 'import sys, yaml; data = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}; print((data.get("server") or {}).get("host") or "0.0.0.0")' "$CONFIG")"
CONFIG_PORT="$("$VENV_DIR/bin/python" -c 'import sys, yaml; data = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}; print((data.get("server") or {}).get("port") or 8000)' "$CONFIG")"
HOST="${HOST:-$CONFIG_HOST}"
PORT="${PORT:-$CONFIG_PORT}"

mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ]; then
  EXISTING_PID="$(cat "$PID_FILE")"
  if [ -n "$EXISTING_PID" ] && kill -0 "$EXISTING_PID" >/dev/null 2>&1; then
    echo "Oniros AI Gateway appears to be running already."
    echo "  pid: $EXISTING_PID"
    echo "  pid_file: $PID_FILE"
    echo "Stop it first: kill $EXISTING_PID"
    exit 1
  fi
  rm -f "$PID_FILE"
fi

if ! "$VENV_DIR/bin/python" - "$HOST" "$PORT" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

probe_host = "" if host in {"0.0.0.0", "::"} else host
family = socket.AF_INET6 if ":" in host else socket.AF_INET

try:
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((probe_host, port))
except PermissionError:
    print(f"Port check failed: permission denied while binding {host}:{port}", file=sys.stderr)
    sys.exit(2)
except OSError as exc:
    print(f"Port check failed: cannot bind {host}:{port}: {exc}", file=sys.stderr)
    sys.exit(1)
PY
then
  echo "Port $PORT is not available on $HOST." >&2
  echo "Check the listener with one of:" >&2
  echo "  sudo ss -ltnp 'sport = :$PORT'" >&2
  echo "  sudo lsof -nP -iTCP:$PORT -sTCP:LISTEN" >&2
  echo "  sudo fuser -v ${PORT}/tcp" >&2
  exit 1
fi

echo "Starting Oniros AI Gateway"
echo "  config: $CONFIG"
echo "  listen: http://$HOST:$PORT"
echo "  log: $LOG_FILE"

if [ "$FOREGROUND" = "1" ]; then
  ONIROS_CONFIG="$CONFIG" exec "$UVICORN" app.main:app --host "$HOST" --port "$PORT"
fi

"$VENV_DIR/bin/python" - "$LOG_FILE" "$PID_FILE" "$CONFIG" "$UVICORN" "$HOST" "$PORT" <<'PY'
import os
import subprocess
import sys

log_file, pid_file, config, uvicorn, host, port = sys.argv[1:]
env = os.environ.copy()
env["ONIROS_CONFIG"] = config

log = open(log_file, "ab", buffering=0)
process = subprocess.Popen(
    [uvicorn, "app.main:app", "--host", host, "--port", port],
    stdin=subprocess.DEVNULL,
    stdout=log,
    stderr=subprocess.STDOUT,
    env=env,
    start_new_session=True,
)

with open(pid_file, "w", encoding="utf-8") as handle:
    handle.write(str(process.pid))
PY

GATEWAY_PID="$(cat "$PID_FILE")"

sleep 1
if ! kill -0 "$GATEWAY_PID" >/dev/null 2>&1; then
  echo "Oniros AI Gateway failed to stay running. Last log lines:" >&2
  tail -40 "$LOG_FILE" >&2 || true
  rm -f "$PID_FILE"
  exit 1
fi

echo "Oniros AI Gateway started in background."
echo "  pid: $GATEWAY_PID"
echo "  pid_file: $PID_FILE"
echo "  log: $LOG_FILE"
echo "  health: http://$HOST:$PORT/health"
