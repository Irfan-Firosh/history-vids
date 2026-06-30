"""Unit tests for studio.run_log.RunRecorder — manifest shape, event flow, run isolation."""

from __future__ import annotations

import json

from studio.run_log import RunManifest, RunRecorder, new_run_id


def _make(tmp_path, **over):
    kw = dict(title="T", images_provider="placeholder", voice_provider="say", scene_count=2)
    kw.update(over)
    return RunRecorder.create(tmp_path / "runs", **kw)


def test_create_writes_running_manifest_and_log(tmp_path):
    rec = _make(tmp_path, run_id="r1")
    assert rec.run_id == "r1"
    manifest = json.loads((rec.dir / "run.json").read_text())
    assert manifest["status"] == "running"
    assert manifest["scene_count"] == 2 and manifest["scenes"] == []
    assert "run r1 started" in (rec.dir / "log.txt").read_text()


def test_scene_lifecycle_updates_manifest(tmp_path):
    rec = _make(tmp_path, run_id="r2")
    rec.scene_started(0, "character", "a cave", ref_count=2)
    rec.scene_image(0, rec.dir / "img_0.png")
    rec.scene_narration(0, 4.25)
    rec.scene_rendered(0, rec.dir / "scene_0.mp4")

    scene = json.loads((rec.dir / "run.json").read_text())["scenes"][0]
    assert scene["status"] == "rendered"
    assert scene["shot_type"] == "character" and scene["ref_count"] == 2
    assert scene["image_path"] == "img_0.png"  # stored relative to the run dir
    assert scene["clip_path"] == "scene_0.mp4"
    assert scene["narration_duration_sec"] == 4.25


def test_completed_records_video_and_duration(tmp_path):
    rec = _make(tmp_path, run_id="r3")
    rec.completed(rec.dir / "video.mp4", 24.84)
    m = RunManifest.model_validate_json((rec.dir / "run.json").read_text())
    assert m.status == "completed" and m.finished_at
    assert m.video_path == "video.mp4" and m.total_duration_sec == 24.84


def test_failed_captures_error_and_logs(tmp_path):
    rec = _make(tmp_path, run_id="r4")
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        rec.failed(exc)
    m = json.loads((rec.dir / "run.json").read_text())
    assert m["status"] == "failed"
    assert m["error"]["message"] == "boom" and "RuntimeError" in m["error"]["traceback"]
    assert "FAILED: boom" in (rec.dir / "log.txt").read_text()


def test_narration_wav_is_not_surfaced_in_manifest(tmp_path):
    """The voice is intentionally excluded — only its duration is recorded, never a .wav path."""
    rec = _make(tmp_path, run_id="r5")
    rec.scene_started(0, "wide", "p")
    rec.scene_narration(0, 3.0)
    blob = (rec.dir / "run.json").read_text()
    assert ".wav" not in blob and "narr_" not in blob


def test_runs_are_isolated_no_overwrite(tmp_path):
    a = _make(tmp_path, run_id="aaa")
    b = _make(tmp_path, run_id="bbb")
    assert a.dir != b.dir
    a.scene_started(0, "character", "only-in-a")
    assert "only-in-a" in (a.dir / "run.json").read_text()
    assert "only-in-a" not in (b.dir / "run.json").read_text()


def test_new_run_id_is_sortable_timestamp():
    rid = new_run_id()
    assert len(rid) == 15 and rid[8] == "-" and rid.replace("-", "").isdigit()
