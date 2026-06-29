"""FastAPI app behind the B&W run dashboard.

Reads the per-run artifacts written by ``studio.RunRecorder`` (``result/axen/poc/runs/<id>/``) and
serves them to a single vanilla-HTML page that polls while a run is active. Can also *trigger* a run
by spawning ``tools/studio_poc.py`` as a background subprocess — one at a time (locked).

Run it:  uv run uvicorn dashboard.app:app --reload  →  http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "result/axen/poc/runs"
INDEX_HTML_PATH = Path(__file__).parent / "index.html"

app = FastAPI(title="Pipeline Run Dashboard")

# A single in-flight run at a time. The pipeline is CPU/ffmpeg heavy and writes a fixed run dir, so
# concurrent triggers would fight; we serialise them and surface a clear 409 instead.
_active: dict[str, object] = {"run_id": None, "proc": None}
_lock = threading.Lock()


# ── helpers ───────────────────────────────────────────────────────────────────
def _run_dir(run_id: str) -> Path:
    """Resolve a run dir, rejecting any id that escapes RUNS_DIR (path-traversal guard)."""
    base = RUNS_DIR.resolve()
    target = (RUNS_DIR / run_id).resolve()
    if not target.is_relative_to(base) or not target.is_dir():
        raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    return target


def _read_manifest(run_dir: Path) -> dict | None:
    path = run_dir / "run.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None  # a mid-flush read can race; the client just polls again


def _is_active(run_id: str, mode: str | None = None) -> bool:
    """True while a subprocess for this run is alive (optionally of a specific mode)."""
    with _lock:
        proc = _active["proc"]
        if proc is None or proc.poll() is not None or _active["run_id"] != run_id:
            return False
        return mode is None or _active.get("mode") == mode


# ── routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index() -> str:
    # Read fresh from disk each request (NOT cached at import): a running server must reflect edits
    # to index.html without a restart — a cached copy silently served stale UI (e.g. before the
    # fire-spot multi-frame view existed). The file is tiny, so a per-request read is free.
    return INDEX_HTML_PATH.read_text(encoding="utf-8")


@app.get("/api/runs")
def list_runs() -> JSONResponse:
    """Newest-first summaries of every recorded run."""
    summaries: list[dict] = []
    if RUNS_DIR.is_dir():
        for child in RUNS_DIR.iterdir():
            if not child.is_dir():
                continue
            m = _read_manifest(child)
            if m is None:
                continue
            rendered = sum(1 for s in m.get("scenes", []) if s.get("status") == "rendered")
            summaries.append(
                {
                    "run_id": m.get("run_id", child.name),
                    "title": m.get("title", ""),
                    "status": m.get("status", "unknown"),
                    "scene_count": m.get("scene_count", 0),
                    "rendered": rendered,
                    "started_at": m.get("started_at"),
                    "finished_at": m.get("finished_at"),
                    "total_duration_sec": m.get("total_duration_sec"),
                }
            )
    summaries.sort(key=lambda s: s["run_id"], reverse=True)
    return JSONResponse(summaries)


@app.get("/api/runs/{run_id}/log", response_class=PlainTextResponse)
def get_log(run_id: str) -> str:
    log = _run_dir(run_id) / "log.txt"
    return log.read_text(encoding="utf-8") if log.is_file() else ""


@app.get("/api/runs/{run_id}/file/{name:path}")
def get_file(run_id: str, name: str) -> FileResponse:
    """Serve an asset (image / video) from inside the run dir, with traversal protection."""
    run_dir = _run_dir(run_id)
    target = (run_dir / name).resolve()
    if not target.is_relative_to(run_dir) or not target.is_file():
        raise HTTPException(status_code=404, detail=f"file {name!r} not found")
    return FileResponse(target)
