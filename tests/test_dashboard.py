"""API tests for the dashboard — listing, manifest/log/file serving, traversal, run locking."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from dashboard import app as dash


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Point the app at a temp runs dir holding one fake completed run."""
    runs = tmp_path / "runs"
    run = runs / "20260101-000000"
    run.mkdir(parents=True)
    manifest = {
        "run_id": "20260101-000000", "title": "Demo", "images_provider": "placeholder",
        "voice_provider": "say", "status": "completed", "scene_count": 1,
        "started_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:05+00:00",
        "finished_at": "2026-01-01T00:00:05+00:00", "total_duration_sec": 5.0,
        "video_path": "video.mp4",
        "scenes": [{"index": 0, "shot_type": "character", "image_prompt": "p", "ref_count": 0,
                    "status": "rendered", "image_path": "img_0.png", "narration_duration_sec": 5.0,
                    "clip_path": "scene_0.mp4", "started_at": "x", "updated_at": "y"}],
    }
    (run / "run.json").write_text(json.dumps(manifest))
    (run / "log.txt").write_text("[ts] run started\n")
    (run / "img_0.png").write_bytes(b"\x89PNG\r\n fake")
    (run / "video.mp4").write_bytes(b"fake-mp4")
    monkeypatch.setattr(dash, "RUNS_DIR", runs)
    monkeypatch.setattr(dash, "_active", {"run_id": None, "proc": None})
    return TestClient(dash.app)


def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200 and "Pipeline Runs" in r.text


def test_new_run_page_serves(client):
    r = client.get("/new")
    assert r.status_code == 200 and "New Run" in r.text


def test_per_role_models_build_command(client, monkeypatch):
    """The new run page's per-role selection maps to --char-model / --concept-model flags."""
    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    r = client.post("/api/runs", json={
        "char_model": "gemini", "concept_model": "agnes", "voice": "cartesia",
    })
    assert r.status_code == 201
    cmd = captured["cmd"]
    assert "--char-model" in cmd and cmd[cmd.index("--char-model") + 1] == "gemini"
    assert cmd[cmd.index("--concept-model") + 1] == "agnes"
    assert "--images" not in cmd  # per-role takes precedence over the legacy shorthand


def test_agnes_is_an_accepted_provider(client, monkeypatch):
    class FakeProc:
        def poll(self):
            return None

    monkeypatch.setattr(dash.subprocess, "Popen", lambda *a, **k: FakeProc())
    assert client.post("/api/runs", json={"images": "agnes"}).status_code == 201


def test_list_runs_summarises(client):
    runs = client.get("/api/runs").json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "20260101-000000" and runs[0]["status"] == "completed"
    assert runs[0]["rendered"] == 1 and runs[0]["scene_count"] == 1


def test_serve_image_and_video(client):
    img = client.get("/api/runs/20260101-000000/file/img_0.png")
    vid = client.get("/api/runs/20260101-000000/file/video.mp4")
    assert img.status_code == 200 and img.content.startswith(b"\x89PNG")
    assert vid.status_code == 200 and vid.content == b"fake-mp4"


def test_traversal_is_blocked(client):
    # Even a crafted name must not escape the run dir.
    r = client.get("/api/runs/20260101-000000/file/..%2f..%2frun.json")
    assert r.status_code == 404


def test_trigger_locks_to_one_run(client, monkeypatch):
    class FakeProc:
        def __init__(self, *a, **k):
            self._done = False

        def poll(self):
            return None if not self._done else 0

    created: list[FakeProc] = []

    def fake_popen(*a, **k):
        p = FakeProc()
        created.append(p)
        return p

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)

    first = client.post("/api/runs", json={"images": "placeholder", "voice": "say"})
    assert first.status_code == 201 and first.json()["run_id"]

    # Second trigger while the first is live → 409.
    assert client.post("/api/runs", json={}).status_code == 409

    # Once the first finishes, a new run is allowed.
    created[0]._done = True
    assert client.post("/api/runs", json={}).status_code == 201


def test_invalid_provider_rejected(client):
    assert client.post("/api/runs", json={"images": "dalle"}).status_code == 422


def test_delete_missing_run_is_404(client):
    assert client.request("DELETE", "/api/runs/nope").status_code == 404


def test_delete_traversal_blocked(client):
    assert client.request("DELETE", "/api/runs/..%2f..%2fetc").status_code == 404


def test_reedit_rejected_without_storyboard(client):
    r = client.post("/api/runs/20260101-000000/reassemble", json={"speed": 0.9})
    assert r.status_code == 400


# ── resume (pick up a stopped/failed run, reusing frames on disk) ──────────────
def _mark_failed_with_storyboard(run_dir, images_provider="gemini/agnes"):
    m = json.loads((run_dir / "run.json").read_text())
    m["status"] = "failed"
    m["images_provider"] = images_provider
    m["voice_provider"] = "cartesia"
    (run_dir / "run.json").write_text(json.dumps(m))
    (run_dir / "storyboard.json").write_text('{"title": "t", "scenes": []}')


def test_resume_rejected_without_storyboard(client):
    m = json.loads((dash.RUNS_DIR / "20260101-000000" / "run.json").read_text())
    m["status"] = "failed"
    (dash.RUNS_DIR / "20260101-000000" / "run.json").write_text(json.dumps(m))
    assert client.post("/api/runs/20260101-000000/resume", json={}).status_code == 400
