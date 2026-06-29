"""Run instrumentation — records a pipeline run as a browsable artifact on disk.

Each run gets its own directory ``<base>/<run_id>/`` holding:
  * ``run.json`` — a structured manifest the dashboard polls (status + per-scene events).
  * ``log.txt``  — a human-readable line log (mirrors the CLI's stdout).
  * the run's own images / clips / final video (no cross-run overwrites → real history).

Pure I/O accumulator: it persists what the pipeline *did* (paths, prompts, timings). It performs
no network or business logic — the side-effecting providers in ``tools/studio_poc.py`` call into it.
The manifest is built from frozen pydantic models and rewritten atomically on every event, so a
half-written ``run.json`` is never observed by a concurrently polling reader.

Narration is recorded as a *duration only* — the ``.wav`` lives in the run dir but is intentionally
left out of the manifest's display fields (the dashboard surfaces images + video, not the voice).
"""

from __future__ import annotations

import os
import traceback
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

#: Lifecycle of a single scene, in order. ``failed`` is terminal for the scene.
SCENE_STATUSES: tuple[str, ...] = ("started", "image_ready", "narrated", "rendered", "failed")
#: Lifecycle of the whole run.
RUN_STATUSES: tuple[str, ...] = ("running", "pending_approval", "completed", "failed")


def _now() -> str:
    """UTC ISO-8601 timestamp (stable, sortable, timezone-aware)."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_run_id() -> str:
    """A filesystem-safe, lexically-sortable run id (local time, second resolution)."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


class SceneRecord(BaseModel):
    """One scene's progress through the pipeline. Paths are relative to the run dir."""

    model_config = ConfigDict(frozen=True)

    index: int
    shot_type: str
    image_prompt: str
    narration: str = ""  # the spoken line (the script beat) — surfaced; the .wav still is not
    cite: tuple[int, ...] = ()  # research-brief [n] indices backing this beat
    emphasis: str = ""  # the on-screen callout for this beat, if any (labels a "callout frame")
    intense: bool = False  # flagged dramatic beat (gets extra frames)
    frame_count: int = 1  # how many distinct frames this beat shows (>1 = a "fire spot" with a cut)
    ref_count: int = 0
    status: str = "started"
    image_path: str | None = None
    narration_duration_sec: float | None = None
    clip_path: str | None = None
    started_at: str
    updated_at: str


class CalloutPlan(BaseModel):
    """One key-fact callout that WILL actually be flashed on screen (post spacing-cap) — so the
    dashboard can show the plan: which text, on which scene's frame, at what time."""

    model_config = ConfigDict(frozen=True)

    text: str
    scene_index: int  # the callout is drawn on this scene's first frame (img_{scene_index}.png)
    start_sec: float


class RunManifest(BaseModel):
    """The full record of a run — exactly what ``run.json`` serialises to."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    title: str
    images_provider: str
    voice_provider: str
    status: str
    scene_count: int
    started_at: str
    updated_at: str
    finished_at: str | None = None
    scenes: tuple[SceneRecord, ...] = ()
    callouts: tuple[CalloutPlan, ...] = ()  # the sparse callouts that render (text · frame · time)
    video_path: str | None = None
    thumbnail_path: str | None = None  # generated YouTube thumbnail (focal image + PIL title)
    total_duration_sec: float | None = None
    error: dict[str, str] | None = None
    resume_note: str | None = None  # set when a run is resumed: what was reused vs regenerated
    # Script-stage artifacts (present when rendered from a generated storyboard) — rel paths the
    # dashboard fetches to show the full pipeline: the script, the Exa sources, the QC fact-check.
    topic: str | None = None
    script_path: str | None = None
    sources_path: str | None = None
    qc_path: str | None = None


class RunRecorder:
    """Accumulates a :class:`RunManifest` on disk, one event at a time.

    Construct with :meth:`create` (makes the dir + initial manifest). Every event method swaps in a
    new immutable manifest and re-flushes ``run.json`` + appends to ``log.txt``.
    """

    MANIFEST_NAME = "run.json"
    LOG_NAME = "log.txt"

    def __init__(self, run_dir: Path, manifest: RunManifest) -> None:
        self._dir = run_dir
        self._manifest = manifest

    # ── construction ──────────────────────────────────────────────────────────
    @classmethod
    def create(
        cls,
        base_dir: Path | str,
        *,
        title: str,
        images_provider: str,
        voice_provider: str,
        scene_count: int,
        run_id: str | None = None,
    ) -> RunRecorder:
        run_id = run_id or new_run_id()
        run_dir = Path(base_dir) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        now = _now()
        manifest = RunManifest(
            run_id=run_id,
            title=title,
            images_provider=images_provider,
            voice_provider=voice_provider,
            status="running",
            scene_count=scene_count,
            started_at=now,
            updated_at=now,
        )
        rec = cls(run_dir, manifest)
        rec._flush()
        rec.log(
            f"run {run_id} started · {title!r} · {scene_count} scenes · "
            f"images={images_provider} voice={voice_provider}"
        )
        return rec

    @classmethod
    def load(cls, base_dir: Path | str, run_id: str) -> RunRecorder:
        """Re-open an EXISTING run's manifest (does NOT reset it). Used by the approve/regenerate
        steps of the review gate, which run as separate processes but must keep the scenes,
        callouts, and history the original render already recorded."""
        run_dir = Path(base_dir) / run_id
        manifest = RunManifest.model_validate_json(
            (run_dir / cls.MANIFEST_NAME).read_text(encoding="utf-8")
        )
        return cls(run_dir, manifest)

    # ── identity / paths ──────────────────────────────────────────────────────
    @property
    def dir(self) -> Path:
        return self._dir

    @property
    def run_id(self) -> str:
        return self._manifest.run_id

    @property
    def manifest(self) -> RunManifest:
        return self._manifest

    def _rel(self, path: Path) -> str:
        """Path relative to the run dir (what the dashboard serves), POSIX-style."""
        return Path(path).relative_to(self._dir).as_posix()

    # ── scene events ──────────────────────────────────────────────────────────
    def scene_started(
        self,
        index: int,
        shot_type: str,
        image_prompt: str,
        ref_count: int = 0,
        narration: str = "",
        cite: tuple[int, ...] = (),
        emphasis: str = "",
        intense: bool = False,
        frame_count: int = 1,
    ) -> None:
        now = _now()
        scene = SceneRecord(
            index=index,
            shot_type=shot_type,
            image_prompt=image_prompt,
            narration=narration,
            cite=cite,
            emphasis=emphasis,
            intense=intense,
            frame_count=max(1, frame_count),
            ref_count=ref_count,
            status="started",
            started_at=now,
            updated_at=now,
        )
        self._append_scene(scene)

    def set_plan(self, *, title: str | None = None, scene_count: int | None = None) -> None:
        """Fill in the real title / scene count once known (the orchestrator researches first)."""
        updates: dict[str, object] = {"updated_at": _now()}
        if title is not None:
            updates["title"] = title
        if scene_count is not None:
            updates["scene_count"] = scene_count
        self._replace(**updates)

    def attach_artifacts(
        self,
        *,
        topic: str | None = None,
        script: Path | None = None,
        sources: Path | None = None,
        qc: Path | None = None,
    ) -> None:
        """Record copied script-stage artifacts (rel paths) so the dashboard can show them."""
        updates: dict[str, object] = {"updated_at": _now()}
        if topic is not None:
            updates["topic"] = topic
        if script is not None:
            updates["script_path"] = self._rel(script)
        if sources is not None:
            updates["sources_path"] = self._rel(sources)
        if qc is not None:
            updates["qc_path"] = self._rel(qc)
        self._replace(**updates)

    def scene_image(self, index: int, image_path: Path) -> None:
        self._update_scene(index, status="image_ready", image_path=self._rel(image_path))

    def scene_narration(self, index: int, duration_sec: float) -> None:
        self._update_scene(index, status="narrated", narration_duration_sec=round(duration_sec, 3))

    def scene_rendered(self, index: int, clip_path: Path) -> None:
        self._update_scene(index, status="rendered", clip_path=self._rel(clip_path))

    def set_callouts(self, callouts: list[tuple[str, int, float]]) -> None:
        """Record the sparse callout plan (text, scene_index, start_sec) that will actually render,
        so the dashboard can show *what* gets flashed and *where* before/while it does."""
        self._replace(
            callouts=tuple(
                CalloutPlan(text=t, scene_index=i, start_sec=round(s, 3)) for t, i, s in callouts
            ),
            updated_at=_now(),
        )

    def set_thumbnail(self, path: Path) -> None:
        """Record the generated thumbnail (rel path) so the dashboard can show + download it."""
        self._replace(thumbnail_path=self._rel(path), updated_at=_now())

    def resumed(self, note: str) -> None:
        """Record (in the manifest + log) what a resumed run reused vs. will regenerate."""
        self._replace(resume_note=note, updated_at=_now())
        self.log(note)

    # ── run terminal events ───────────────────────────────────────────────────
    def pending_approval(self) -> None:
        now = _now()
        self._replace(
            status="pending_approval",
            updated_at=now,
        )

    def completed(self, video_path: Path, total_duration_sec: float) -> None:
        now = _now()
        self._replace(
            status="completed",
            finished_at=now,
            updated_at=now,
            video_path=self._rel(video_path),
            total_duration_sec=round(total_duration_sec, 3),
        )

    def failed(self, exc: BaseException) -> None:
        now = _now()
        self._replace(
            status="failed",
            finished_at=now,
            updated_at=now,
            error={"message": str(exc), "traceback": traceback.format_exc()},
        )
        self.log(f"FAILED: {exc}")

    # ── logging ───────────────────────────────────────────────────────────────
    def log(self, message: str) -> None:
        """Append a timestamped line to ``log.txt`` (the dashboard tails this)."""
        line = f"[{_now()}] {message}\n"
        with (self._dir / self.LOG_NAME).open("a", encoding="utf-8") as fh:
            fh.write(line)

    # ── internals ─────────────────────────────────────────────────────────────
    def _append_scene(self, scene: SceneRecord) -> None:
        self._replace(scenes=(*self._manifest.scenes, scene), updated_at=_now())

    def _update_scene(self, index: int, **fields: object) -> None:
        scenes = tuple(
            s.model_copy(update={**fields, "updated_at": _now()}) if s.index == index else s
            for s in self._manifest.scenes
        )
        self._replace(scenes=scenes, updated_at=_now())

    def _replace(self, **fields: object) -> None:
        self._manifest = self._manifest.model_copy(update=fields)
        self._flush()

    def _flush(self) -> None:
        """Atomically rewrite ``run.json`` (tmp + os.replace) so readers never see a partial."""
        target = self._dir / self.MANIFEST_NAME
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(self._manifest.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, target)
