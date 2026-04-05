#!/usr/bin/env bash
# Start the Gold Signal FastAPI app. Run from anywhere; script cds to repo root.
# If port is busy: kill the old server, e.g.  kill $(lsof -t -iTCP:8000 -sTCP:LISTEN)
# Or use another port:  GOLD_API_PORT=8001 ./scripts/start_api.sh
#   (set the same port in frontend/.env as VITE_API_PORT=8001)
# Latest tuning overlays (WF τ + category weights from data/tuning_runs/):
#   GOLD_USE_LATEST_TUNING=1
#   GOLD_TUNING_RUN_DIR=/abs/path/to/data/tuning_runs/<run>   # optional; overrides “latest” folder
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=backend

PORT="${GOLD_API_PORT:-8000}"
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: port $PORT is already in use."
  echo "Usually another uvicorn is still running. Stop it, e.g.:"
  echo "  kill \$(lsof -t -iTCP:$PORT -sTCP:LISTEN)"
  echo "Or pick another port for the API (and set VITE_API_PORT in frontend/.env to match):"
  echo "  GOLD_API_PORT=8001 $0"
  exit 1
fi

exec python3 -m uvicorn gold_signal.api.main:app --reload --host 127.0.0.1 --port "$PORT"
