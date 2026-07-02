#!/usr/bin/env bash
# Start the pipeline run dashboard (FastAPI + uvicorn).
# Usage: ./start-dashboard.sh [port] [--dev]
#   default port 8000. --dev enables --reload (auto-restart on code changes). Do NOT use --dev while
#   real renders run: a reload restarts the server (renders are detached and survive, but the
#   in-memory single-run lock resets). For production runs, start it WITHOUT --dev.
set -euo pipefail
cd "$(dirname "$0")"

PORT="8000"
RELOAD=""
for arg in "$@"; do
  case "$arg" in
    --dev) RELOAD="--reload" ;;
    *) PORT="$arg" ;;
  esac
done

echo "▶ Pipeline dashboard → http://127.0.0.1:${PORT}   (Ctrl+C to stop)${RELOAD:+  [dev/reload]}"
exec uv run uvicorn dashboard.app:app --host 127.0.0.1 --port "${PORT}" ${RELOAD}
