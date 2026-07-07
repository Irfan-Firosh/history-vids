"""FastAPI app behind the B&W run dashboard.

Reads the per-run artifacts written by ``studio.RunRecorder`` (``result/axen/poc/runs/<id>/``) and
serves them to a single vanilla-HTML page that polls while a run is active. Can also *trigger* a run
by spawning ``tools/studio_poc.py`` as a background subprocess — one at a time (locked).

Run it:  uv run uvicorn dashboard.app:app --reload  →  http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Literal, get_args

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from studio import new_run_id

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "result/axen/poc/runs"
POC_SCRIPT = REPO_ROOT / "tools/studio_poc.py"
PIPELINE_SCRIPT = REPO_ROOT / "tools/run_pipeline.py"  # topic → script → render (whole pipeline)
REASSEMBLE_SCRIPT = REPO_ROOT / "tools/reassemble.py"  # re-edit: fresh Cartesia TTS + retimed cuts
REEDIT_VIDEO = "video_v2.mp4"  # reassemble output (kept beside the original video.mp4)
INDEX_HTML_PATH = Path(__file__).parent / "index.html"
NEW_RUN_HTML_PATH = Path(__file__).parent / "new_run.html"

app = FastAPI(title="Pipeline Run Dashboard")

# A single in-flight run at a time. The pipeline is CPU/ffmpeg heavy and writes a fixed run dir, so
# concurrent triggers would fight; we serialise them and surface a clear 409 instead.
_active: dict[str, object] = {"run_id": None, "proc": None}
_lock = threading.Lock()


ImageModel = Literal["placeholder", "gemini", "agnes", "hf", "cloudflare"]
_IMAGE_MODELS: tuple[str, ...] = get_args(ImageModel)  # valid provider names (re-run coercion)


class RunRequest(BaseModel):
    """Trigger payload — providers are constrained to the pipeline's known choices.

    With ``topic`` set, the whole pipeline runs (topic → Exa+LLM script → render); without it, the
    canned demo storyboard is rendered. ``images`` is the legacy single-provider shorthand (the main
    page); the new run page instead sets per-role models (``char_model`` / ``concept_model``) — when
    either is set it takes precedence over ``images``.
    """

    topic: str | None = None
    images: ImageModel = "placeholder"
    char_model: ImageModel | None = None
    concept_model: ImageModel | None = None
    voice: Literal["say", "cartesia"] = "say"
    captions: bool = True
    min_minutes: float = 6.0  # target duration band (topic runs only)
    max_minutes: float = 9.0
    # Human-in-the-loop: pause after images so the user can review/regenerate before assembly.
    # On for topic runs by default (the demo has no real images worth reviewing).
    review: bool = True


class ReassembleRequest(BaseModel):
    """Re-edit payload — only the Cartesia narration speed is tunable (images are reused as-is)."""

    speed: float = 0.88  # Cartesia generation_config.speed, clamped to [0.6, 1.5]


class ResumeRequest(BaseModel):
    """Resume payload — reuse frames on disk; subtitles can be toggled on the resume."""

    captions: bool = True


class ApproveRequest(BaseModel):
    """Approve payload — assemble the reviewed images into the final video."""

    captions: bool = True


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


def _reedit_state(run_dir: Path, run_id: str, manifest: dict) -> dict:
    """Whether this run CAN be re-edited (has a saved storyboard + images), and the re-edit output.

    A re-edit reruns only the Cartesia TTS + retimed assembly on the images already on disk, so it
    needs a ``storyboard.json`` (the narration) and at least the first image. Demo runs lack these.
    Hidden while a run is awaiting review approval (Approve is the action there, not Re-edit).
    """
    return {
        "available": (
            (run_dir / "storyboard.json").is_file()
            and (run_dir / "img_0.png").is_file()
            and manifest.get("status") != "pending_approval"
        ),
        "video": REEDIT_VIDEO if (run_dir / REEDIT_VIDEO).is_file() else None,
        "running": _is_active(run_id, "reassemble"),
    }


def _resume_state(run_dir: Path, run_id: str, manifest: dict) -> dict:
    """Whether a stopped/failed run can be resumed (reuse frames already on disk).

    Needs a saved ``storyboard.json``; only offered for runs that aren't finished and aren't the
    live process (a failed or interrupted run). Hidden while awaiting review approval — the images
    are already all there; the pending action is Approve, not Resume.
    """
    running = _is_active(run_id)
    resumable = (
        (run_dir / "storyboard.json").is_file()
        and manifest.get("status") not in ("completed", "pending_approval")
        and not running
    )
    return {"available": resumable, "running": _is_active(run_id, "resume")}


def _approval_state(run_dir: Path, run_id: str, manifest: dict) -> dict:
    """Drives the review UI. ``available`` = awaiting approval (show Approve). ``editable`` = the
    per-scene Regenerate controls can be shown — true at the review gate AND on a finished run
    (tweak an image post-hoc; regenerating drops it back to pending_approval so Approve rebuilds).
    Plus whether an approve (assemble) / regenerate job is currently running."""
    status = manifest.get("status")
    has_content = (run_dir / "storyboard.json").is_file() and (run_dir / "img_0.png").is_file()
    return {
        "available": status == "pending_approval" and (run_dir / "storyboard.json").is_file(),
        "editable": has_content and status in ("pending_approval", "completed")
        and not _is_active(run_id),
        "assembling": _is_active(run_id, "assemble"),
        "regenerating": _is_active(run_id, "regenerate"),
    }


# ── routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index() -> str:
    # Read fresh from disk each request (NOT cached at import): a running server must reflect edits
    # to index.html without a restart — a cached copy silently served stale UI (e.g. before the
    # fire-spot multi-frame view existed). The file is tiny, so a per-request read is free.
    return INDEX_HTML_PATH.read_text(encoding="utf-8")


@app.get("/new", response_class=HTMLResponse)
def new_run_page() -> str:
    """Separate run-configuration page: per-role model pickers + a Recommended preset."""
    return NEW_RUN_HTML_PATH.read_text(encoding="utf-8")


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


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str) -> dict[str, str]:
    """Delete a run's directory. Refuses to delete the run that's currently in progress."""
    with _lock:
        proc = _active["proc"]
        if _active["run_id"] == run_id and proc is not None and proc.poll() is None:
            raise HTTPException(status_code=409, detail="run is still in progress")
    run_dir = _run_dir(run_id)  # 404 + traversal-guarded
    shutil.rmtree(run_dir)
    return {"deleted": run_id}


def _spawn_run(req: RunRequest) -> str:
    """Spawn a pipeline (or canned-demo) run in the background under the single-run lock; return the
    new run_id. Raises 409 if a run is already live. Shared by the trigger + re-run endpoints."""
    with _lock:
        proc = _active["proc"]
        if proc is not None and proc.poll() is None:  # poll() is None ⇒ still running
            raise HTTPException(
                status_code=409, detail=f"run {_active['run_id']} still in progress"
            )

        run_id = new_run_id()
        topic = (req.topic or "").strip()
        script = PIPELINE_SCRIPT if topic else POC_SCRIPT  # whole pipeline vs canned demo
        cmd = [sys.executable, str(script), "--run-id", run_id, "--voice", req.voice]
        if topic:  # whole pipeline: pass topic + the target duration band
            cmd[2:2] = [
                "--topic", topic,
                "--min-minutes", str(req.min_minutes), "--max-minutes", str(req.max_minutes),
            ]
            if req.review:  # pause after images for human review/approval (topic runs only)
                cmd.append("--review")
        # Per-role model selection (new run page) takes precedence over the legacy single --images.
        if req.char_model or req.concept_model:
            base = req.images
            cmd += [
                "--char-model", req.char_model or base,
                "--concept-model", req.concept_model or base,
            ]
        else:
            cmd += ["--images", req.images]
        if not req.captions:
            cmd.append("--no-captions")
        # Logs land in the run's log.txt via the recorder; drop the subprocess' own stdio.
        # start_new_session: detach into its own process group so a dashboard reload/restart/crash
        # does NOT kill an in-flight render (a long topic run outlives the server).
        proc = subprocess.Popen(
            cmd, cwd=str(REPO_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _active.update(run_id=run_id, proc=proc, mode="pipeline")
        return run_id


@app.post("/api/runs", status_code=201)
def trigger_run(req: RunRequest) -> dict[str, str]:
    """Spawn a pipeline run in the background; return its run_id to poll. 409 if one is live."""
    return {"run_id": _spawn_run(req)}


@app.post("/api/runs/{run_id}/reassemble", status_code=202)
def reassemble_run(run_id: str, req: ReassembleRequest) -> dict[str, object]:
    """Re-edit a saved run: fresh Cartesia TTS + retimed image/caption cuts, reusing its images.

    Regenerates NO images — only a new narration + assembly → ``video_v2.mp4`` in the run dir.
    Serialised behind the same single-run lock as a full run; progress lands in ``reassemble.log``.
    """
    run_dir = _run_dir(run_id)  # 404 + traversal-guarded
    storyboard = run_dir / "storyboard.json"
    if not storyboard.is_file() or not (run_dir / "img_0.png").is_file():
        raise HTTPException(
            status_code=400, detail="run has no saved storyboard + images to re-edit"
        )
    speed = max(0.6, min(1.5, req.speed))

    with _lock:
        proc = _active["proc"]
        if proc is not None and proc.poll() is None:
            raise HTTPException(
                status_code=409, detail=f"run {_active['run_id']} still in progress"
            )
        cmd = [
            sys.executable, str(REASSEMBLE_SCRIPT),
            "--storyboard", str(storyboard),
            "--images-dir", str(run_dir),
            "--out", str(run_dir / REEDIT_VIDEO),
        ]
        log = (run_dir / "reassemble.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd, cwd=str(REPO_ROOT), stdout=log, stderr=subprocess.STDOUT,
            env={**os.environ, "CARTESIA_SPEED": str(speed)}, start_new_session=True,
        )
        log.close()  # the child holds its own dup of the fd
        _active.update(run_id=run_id, proc=proc, mode="reassemble")
    return {"run_id": run_id, "reassembling": True, "speed": speed}


@app.post("/api/runs/{run_id}/resume", status_code=202)
def resume_run(run_id: str, req: ResumeRequest) -> dict[str, object]:
    """Resume a stopped/failed run: re-render reusing the frames already on disk (``--resume``).

    Reconstructs the run's providers from its manifest and adds a fallback model for any frame the
    primary refuses, so a mid-cycle stop can be picked up without redoing completed frames.
    """
    run_dir = _run_dir(run_id)  # 404 + traversal-guarded
    storyboard = run_dir / "storyboard.json"
    if not storyboard.is_file():
        raise HTTPException(status_code=400, detail="run has no saved storyboard to resume")
    manifest = _read_manifest(run_dir) or {}
    provider = str(manifest.get("images_provider") or "gemini")
    voice = "cartesia" if str(manifest.get("voice_provider", "")).startswith("cartesia") else "say"

    with _lock:
        proc = _active["proc"]
        if proc is not None and proc.poll() is None:
            raise HTTPException(
                status_code=409, detail=f"run {_active['run_id']} still in progress"
            )
        cmd = [
            sys.executable, str(POC_SCRIPT),
            "--storyboard", str(storyboard), "--run-id", run_id, "--resume", "--voice", voice,
        ]
        # Reconstruct the image providers ("char/concept" per-role, else a single --images mode).
        if "/" in provider:
            char, concept = (provider.split("/") + [provider])[:2]
            cmd += ["--char-model", char, "--concept-model", concept]
        else:
            char = provider
            cmd += ["--images", provider]
        # Fallback for refused frames: a different reliable model than the primary character model.
        cmd += ["--fallback", "agnes" if char == "gemini" else "gemini"]
        if not req.captions:
            cmd.append("--no-captions")
        log = (run_dir / "resume.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd, cwd=str(REPO_ROOT), stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        log.close()
        _active.update(run_id=run_id, proc=proc, mode="resume")
    return {"run_id": run_id, "resuming": True, "captions": req.captions}


@app.post("/api/runs/{run_id}/approve", status_code=202)
def approve_run(run_id: str, req: ApproveRequest) -> dict[str, object]:
    """Approve a reviewed run: assemble the final video from the images + narration already on disk.

    The human-in-the-loop gate — a topic run pauses at ``pending_approval`` after generating every
    image; NOTHING is compiled until this is called. Reuses the exact narration + frames (no regen,
    no new TTS); progress lands in ``assemble.log``.
    """
    run_dir = _run_dir(run_id)  # 404 + traversal-guarded
    storyboard = run_dir / "storyboard.json"
    manifest = _read_manifest(run_dir) or {}
    if manifest.get("status") != "pending_approval" or not storyboard.is_file():
        raise HTTPException(status_code=400, detail="run is not awaiting approval")

    with _lock:
        proc = _active["proc"]
        if proc is not None and proc.poll() is None:
            raise HTTPException(
                status_code=409, detail=f"run {_active['run_id']} still in progress"
            )
        cmd = [
            sys.executable, str(POC_SCRIPT),
            "--assemble-only", "--storyboard", str(storyboard), "--run-id", run_id,
        ]
        if not req.captions:
            cmd.append("--no-captions")
        log = (run_dir / "assemble.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd, cwd=str(REPO_ROOT), stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        log.close()
        _active.update(run_id=run_id, proc=proc, mode="assemble")
    return {"run_id": run_id, "assembling": True}
