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

from studio import RunRecorder, new_run_id
from studio.run_log import RunSettings
from studio.script_rubric import (
    MAX_FIRST_QUESTION_SEC,
    MAX_LONG_SENTENCE_PCT,
    MAX_MEAN_SENTENCE_WORDS,
    MIN_SHORT_SENTENCE_PCT,
)

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

#: Rubric thresholds surfaced to the dashboard, read from the real constants in
#: studio.script_rubric — never a second hardcoded copy, so the UI's pass/fail bars can't drift
#: from what the rubric actually enforces.
_RUBRIC_THRESHOLDS: dict[str, float] = {
    "max_first_question_sec": MAX_FIRST_QUESTION_SEC,
    "max_mean_sentence_words": MAX_MEAN_SENTENCE_WORDS,
    "min_short_sentence_pct": MIN_SHORT_SENTENCE_PCT,
    "max_long_sentence_pct": MAX_LONG_SENTENCE_PCT,
}


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
    """Resume payload — reuse frames on disk; subtitles default to the original run's recorded
    settings but can be overridden on the resume."""

    captions: bool | None = None


class ApproveRequest(BaseModel):
    """Approve payload — assemble the reviewed images into the final video."""

    captions: bool = True


class RegenerateRequest(BaseModel):
    """Regenerate payload — re-draw one scene's image(s), optionally with an edited prompt."""

    scene_index: int
    prompt: str | None = None


class ThumbnailRequest(BaseModel):
    """Thumbnail payload — big title words + optional focal subject (both default from the run)."""

    text: str | None = None
    subject: str | None = None


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


def _read_text(path: Path) -> str | None:
    """Read a run-dir text file if present; None (never a 500) when it's missing or unreadable —
    the dashboard shows historical runs recorded before the file existed."""
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _read_json(path: Path) -> dict | None:
    """Read a run-dir JSON file if present; None (never a 500) for a missing/mid-write/corrupt
    file — same defensive contract as ``_read_manifest``."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


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


def _thumbnail_state(run_dir: Path, run_id: str, manifest: dict) -> dict:
    """Whether a thumbnail can be generated for this run (it has generated images) + job status."""
    return {
        "available": (run_dir / "img_0.png").is_file(),
        "running": _is_active(run_id, "thumbnail"),
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


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> JSONResponse:
    run_dir = _run_dir(run_id)
    manifest = _read_manifest(run_dir)
    if manifest is None:
        raise HTTPException(status_code=404, detail="manifest not ready")
    manifest["reedit"] = _reedit_state(run_dir, run_id, manifest)  # drives the Re-edit control
    manifest["resume"] = _resume_state(run_dir, run_id, manifest)  # drives the Resume control
    manifest["approval"] = _approval_state(run_dir, run_id, manifest)  # drives the Approve UI
    manifest["thumbnail"] = _thumbnail_state(run_dir, run_id, manifest)  # drives the Thumbnail UI
    return JSONResponse(manifest)


@app.get("/api/runs/{run_id}/log", response_class=PlainTextResponse)
def get_log(run_id: str) -> str:
    log = _run_dir(run_id) / "log.txt"
    return log.read_text(encoding="utf-8") if log.is_file() else ""


@app.get("/api/runs/{run_id}/prompts")
def get_prompts(run_id: str) -> JSONResponse:
    """The rendered script prompt + every scene's image prompt — the paper trail behind what was
    asked and what was drawn. ``script_prompt`` is null for runs recorded before
    ``script_prompt.txt`` was persisted (see ``tools/make_script.py::build_and_save``); the image
    prompts always come straight from the manifest's scene records, old runs included."""
    run_dir = _run_dir(run_id)  # 404 + traversal-guarded
    manifest = _read_manifest(run_dir) or {}
    image_prompts = [
        {
            "index": s.get("index"),
            "shot_type": s.get("shot_type"),
            "prompt": s.get("image_prompt"),
            "image_path": s.get("image_path"),
            "status": s.get("status"),
            "narration": s.get("narration", ""),
        }
        for s in manifest.get("scenes", [])
    ]
    return JSONResponse({
        "script_prompt": _read_text(run_dir / "script_prompt.txt"),
        "image_prompts": image_prompts,
    })


@app.get("/api/runs/{run_id}/rubric")
def get_rubric(run_id: str) -> JSONResponse:
    """The script-craft rubric report, scored against the thresholds in ``studio.script_rubric``.

    ``ok``/``metrics``/``failures`` are null for runs recorded before ``rubric.json`` was persisted
    (see ``tools/make_script.py::build_and_save``); ``thresholds`` is static config, not per-run
    data, so it's always populated even with no report to show it against.
    """
    run_dir = _run_dir(run_id)  # 404 + traversal-guarded
    data = _read_json(run_dir / "rubric.json")
    if data is None:
        return JSONResponse(
            {"ok": None, "metrics": None, "thresholds": _RUBRIC_THRESHOLDS, "failures": None}
        )
    failures = list(data.get("failures") or [])
    metrics = {k: v for k, v in data.items() if k != "failures"}
    return JSONResponse(
        {"ok": not failures, "metrics": metrics, "thresholds": _RUBRIC_THRESHOLDS,
         "failures": failures}
    )


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
            provider_label = f"{req.char_model or base}/{req.concept_model or base}"
            cmd += [
                "--char-model", req.char_model or base,
                "--concept-model", req.concept_model or base,
            ]
        else:
            provider_label = req.images
            cmd += ["--images", req.images]
        if not req.captions:
            cmd.append("--no-captions")

        # Persist the operator's choices onto the manifest before the pipeline subprocess starts,
        # so a later re-run/resume of THIS run can recover them (rerun_run / resume_run below read
        # `settings` back) instead of silently falling back to defaults.
        settings = RunSettings(
            captions=req.captions,
            min_minutes=req.min_minutes if topic else None,
            max_minutes=req.max_minutes if topic else None,
            images_provider=provider_label,
            voice=req.voice,
        )
        rec = RunRecorder.create(
            RUNS_DIR, title=topic or "(untitled)", images_provider=provider_label,
            voice_provider=req.voice, scene_count=0, run_id=run_id,
        )
        rec.set_settings(settings)

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


@app.post("/api/runs/{run_id}/rerun", status_code=201)
def rerun_run(run_id: str) -> dict[str, str]:
    """Start a FRESH run (new id) that reuses this run's topic + image providers + voice, then
    regenerates everything from scratch — a new script and new images — unlike Resume (reuse the
    frames on disk) or Re-edit (reuse images, new audio). 409 if a run is already live.

    The topic and provider mix (the parts that define the run) are reconstructed from the source
    run's top-level fields; captions are recovered from its recorded `settings` (defaulting to True
    for runs recorded before that field existed).
    """
    run_dir = _run_dir(run_id)  # 404 + traversal-guarded
    manifest = _read_manifest(run_dir) or {}
    provider = str(manifest.get("images_provider") or "placeholder")
    voice = "cartesia" if str(manifest.get("voice_provider", "")).startswith("cartesia") else "say"
    settings = manifest.get("settings") or {}
    kwargs: dict[str, object] = {
        "topic": manifest.get("topic") or None,
        "voice": voice,
        "captions": bool(settings.get("captions", True)),
    }
    if "/" in provider:  # per-role "char/concept" → separate model flags
        char, concept = (provider.split("/") + [provider])[:2]
        kwargs["char_model"] = char if char in _IMAGE_MODELS else "placeholder"
        kwargs["concept_model"] = concept if concept in _IMAGE_MODELS else "placeholder"
    else:  # legacy single-provider shorthand
        kwargs["images"] = provider if provider in _IMAGE_MODELS else "placeholder"
    return {"run_id": _spawn_run(RunRequest(**kwargs))}


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
    settings = manifest.get("settings") or {}
    # An explicit choice on the resume request wins; otherwise recover the original run's choice
    # (defaulting to True for runs recorded before `settings` existed).
    captions = req.captions if req.captions is not None else bool(settings.get("captions", True))

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
        if not captions:
            cmd.append("--no-captions")
        log = (run_dir / "resume.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd, cwd=str(REPO_ROOT), stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        log.close()
        _active.update(run_id=run_id, proc=proc, mode="resume")
    return {"run_id": run_id, "resuming": True, "captions": captions}


def _image_provider_flags(provider: str) -> tuple[list[str], str]:
    """Reconstruct the CLI image-provider flags from a manifest's ``images_provider`` label, plus
    the character provider name (to pick a distinct fallback). E.g. ``gemini/agnes`` → per-role."""
    if "/" in provider:
        char, concept = (provider.split("/") + [provider])[:2]
        return ["--char-model", char, "--concept-model", concept], char
    return ["--images", provider], provider


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


@app.post("/api/runs/{run_id}/regenerate", status_code=202)
def regenerate_scene(run_id: str, req: RegenerateRequest) -> dict[str, object]:
    """Re-draw ONE scene's image(s), optionally with an edited prompt — during the review gate OR on
    an already-finished run.

    Reconstructs the run's image providers from its manifest, overwrites that scene's frame(s), and
    leaves the run in ``pending_approval`` (so a completed run drops back into the gate → Approve
    rebuilds the video with the new image). Needs a saved storyboard + generated images; the single-
    run lock (409) prevents regenerating while another job is live.
    """
    run_dir = _run_dir(run_id)  # 404 + traversal-guarded
    storyboard = run_dir / "storyboard.json"
    manifest = _read_manifest(run_dir) or {}
    if not storyboard.is_file() or not (run_dir / "img_0.png").is_file():
        raise HTTPException(status_code=400, detail="run has no saved storyboard + images to edit")
    if req.scene_index < 0:
        raise HTTPException(status_code=400, detail="scene_index must be >= 0")
    provider = str(manifest.get("images_provider") or "gemini")
    provider_flags, char = _image_provider_flags(provider)

    with _lock:
        proc = _active["proc"]
        if proc is not None and proc.poll() is None:
            raise HTTPException(
                status_code=409, detail=f"run {_active['run_id']} still in progress"
            )
        cmd = [
            sys.executable, str(POC_SCRIPT),
            "--regenerate", str(req.scene_index),
            "--storyboard", str(storyboard), "--run-id", run_id, "--voice", "say",
            *provider_flags,
            "--fallback", "agnes" if char == "gemini" else "gemini",
        ]
        if req.prompt:
            cmd += ["--prompt", req.prompt]
        log = (run_dir / "regenerate.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd, cwd=str(REPO_ROOT), stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        log.close()
        _active.update(run_id=run_id, proc=proc, mode="regenerate")
    return {"run_id": run_id, "regenerating": True, "scene_index": req.scene_index}


@app.post("/api/runs/{run_id}/thumbnail", status_code=202)
def generate_thumbnail(run_id: str, req: ThumbnailRequest) -> dict[str, object]:
    """Generate a YouTube thumbnail for a run: a focal image (the run's provider) + a big PIL title
    overlay. Title defaults to the run's title; both title and focal subject can be overridden."""
    run_dir = _run_dir(run_id)  # 404 + traversal-guarded
    manifest = _read_manifest(run_dir) or {}
    provider = str(manifest.get("images_provider") or "agnes")
    provider_flags, _char = _image_provider_flags(provider)
    text = (req.text or manifest.get("title") or "").strip()

    with _lock:
        proc = _active["proc"]
        if proc is not None and proc.poll() is None:
            raise HTTPException(
                status_code=409, detail=f"run {_active['run_id']} still in progress"
            )
        cmd = [
            sys.executable, str(POC_SCRIPT),
            "--thumbnail", "--run-id", run_id, "--voice", "say", *provider_flags,
        ]
        storyboard = run_dir / "storyboard.json"
        if storyboard.is_file():  # gives the thumbnail the real title + scenes for the subject
            cmd += ["--storyboard", str(storyboard)]
        if text:
            cmd += ["--thumb-text", text]
        if req.subject:
            cmd += ["--thumb-subject", req.subject]
        log = (run_dir / "thumbnail.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd, cwd=str(REPO_ROOT), stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        log.close()
        _active.update(run_id=run_id, proc=proc, mode="thumbnail")
    return {"run_id": run_id, "generating_thumbnail": True}
