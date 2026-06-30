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


def test_delete_missing_run_is_404(client):
    assert client.request("DELETE", "/api/runs/nope").status_code == 404


def test_delete_traversal_blocked(client):
    assert client.request("DELETE", "/api/runs/..%2f..%2fetc").status_code == 404
