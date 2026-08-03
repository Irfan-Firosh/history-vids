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


def test_get_manifest_and_log(client):
    assert client.get("/api/runs/20260101-000000").json()["title"] == "Demo"
    assert "run started" in client.get("/api/runs/20260101-000000/log").text


def test_serve_image_and_video(client):
    img = client.get("/api/runs/20260101-000000/file/img_0.png")
    vid = client.get("/api/runs/20260101-000000/file/video.mp4")
    assert img.status_code == 200 and img.content.startswith(b"\x89PNG")
    assert vid.status_code == 200 and vid.content == b"fake-mp4"


def test_missing_run_is_404(client):
    assert client.get("/api/runs/nope").status_code == 404
    assert client.get("/api/runs/20260101-000000/file/secret.txt").status_code == 404


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


# ── re-run (fresh run reusing this run's topic + providers + voice) ────────────
def test_rerun_reconstructs_topic_and_providers(client, monkeypatch):
    run = dash.RUNS_DIR / "20260101-000000"
    m = json.loads((run / "run.json").read_text())
    m.update(images_provider="gemini/agnes", voice_provider="cartesia", topic="Battle of Tsushima")
    (run / "run.json").write_text(json.dumps(m))

    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    r = client.post("/api/runs/20260101-000000/rerun")
    assert r.status_code == 201 and r.json()["run_id"] != "20260101-000000"  # a brand-new run id
    cmd = captured["cmd"]
    assert cmd[cmd.index("--topic") + 1] == "Battle of Tsushima"  # topic reused → whole pipeline
    assert cmd[cmd.index("--char-model") + 1] == "gemini"
    assert cmd[cmd.index("--concept-model") + 1] == "agnes"
    assert cmd[cmd.index("--voice") + 1] == "cartesia"
    assert "--resume" not in cmd  # a re-run regenerates from scratch, unlike resume


def test_rerun_locks_to_one_run(client, monkeypatch):
    class FakeProc:
        def poll(self):
            return None  # stays alive

    monkeypatch.setattr(dash.subprocess, "Popen", lambda *a, **k: FakeProc())
    assert client.post("/api/runs/20260101-000000/rerun").status_code == 201
    # A second trigger while the re-run is live → 409.
    assert client.post("/api/runs/20260101-000000/rerun").status_code == 409


def test_rerun_missing_run_is_404(client):
    assert client.post("/api/runs/nope/rerun").status_code == 404


def test_rerun_inherits_captions_off_from_manifest_settings(client, monkeypatch):
    """A re-run must inherit the original run's captions choice from `settings`, not silently
    default to True — this is the gap task 1.2 closes (see dashboard/app.py:328's old comment)."""
    run = dash.RUNS_DIR / "20260101-000000"
    m = json.loads((run / "run.json").read_text())
    m["settings"] = {"captions": False}
    (run / "run.json").write_text(json.dumps(m))

    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    r = client.post("/api/runs/20260101-000000/rerun")
    assert r.status_code == 201
    assert "--no-captions" in captured["cmd"]


def test_rerun_defaults_captions_on_when_settings_absent(client, monkeypatch):
    """An old manifest recorded before this change has no `settings` key at all — the re-run must
    still work and fall back to captions=True rather than crashing or silently disabling them."""
    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    r = client.post("/api/runs/20260101-000000/rerun")
    assert r.status_code == 201
    assert "--no-captions" not in captured["cmd"]


# ── review gate (HITL: pause after images → approve to assemble / regenerate one image) ──
def _mark_pending_approval(run_dir, images_provider="gemini/agnes"):
    m = json.loads((run_dir / "run.json").read_text())
    m["status"] = "pending_approval"
    m["images_provider"] = images_provider
    (run_dir / "run.json").write_text(json.dumps(m))
    (run_dir / "storyboard.json").write_text('{"title": "t", "scenes": []}')


def test_topic_run_pauses_for_review_by_default(client, monkeypatch):
    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    r = client.post("/api/runs", json={"topic": "Battle of Tsushima", "images": "agnes"})
    assert r.status_code == 201
    assert "--review" in captured["cmd"]  # topic runs pause for approval by default


def test_demo_run_does_not_pause_for_review(client, monkeypatch):
    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    client.post("/api/runs", json={"images": "placeholder"})  # no topic → canned demo
    assert "--review" not in captured["cmd"]


def test_approve_gated_and_spawns_assemble(client, monkeypatch):
    run = dash.RUNS_DIR / "20260101-000000"
    _mark_pending_approval(run)
    assert client.get("/api/runs/20260101-000000").json()["approval"]["available"] is True

    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    r = client.post("/api/runs/20260101-000000/approve", json={})
    assert r.status_code == 202 and r.json()["assembling"] is True
    assert "--assemble-only" in captured["cmd"]


def test_approve_rejected_when_not_pending(client):
    # the fixture run is completed → not awaiting approval
    assert client.post("/api/runs/20260101-000000/approve", json={}).status_code == 400


def test_regenerate_spawns_with_scene_and_providers(client, monkeypatch):
    run = dash.RUNS_DIR / "20260101-000000"
    _mark_pending_approval(run, images_provider="gemini/agnes")

    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    r = client.post("/api/runs/20260101-000000/regenerate", json={"scene_index": 2})
    assert r.status_code == 202 and r.json()["scene_index"] == 2
    cmd = captured["cmd"]
    assert cmd[cmd.index("--regenerate") + 1] == "2"
    assert cmd[cmd.index("--char-model") + 1] == "gemini"
    assert cmd[cmd.index("--concept-model") + 1] == "agnes"
    assert cmd[cmd.index("--fallback") + 1] == "agnes"  # distinct from the gemini char provider


def test_regenerate_rejected_without_storyboard(client):
    # the fixture run has img_0 but no storyboard.json → nothing to reconstruct scenes from
    r = client.post("/api/runs/20260101-000000/regenerate", json={"scene_index": 0})
    assert r.status_code == 400


def test_regenerate_allowed_on_completed_run(client, monkeypatch):
    # You can tweak an image on a FINISHED run too (it drops back to the review gate for Approve).
    run = dash.RUNS_DIR / "20260101-000000"
    (run / "storyboard.json").write_text('{"title": "t", "scenes": []}')  # status stays "completed"
    assert client.get("/api/runs/20260101-000000").json()["approval"]["editable"] is True

    class FakeProc:
        def poll(self):
            return None

    monkeypatch.setattr(dash.subprocess, "Popen", lambda *a, **k: FakeProc())
    r = client.post("/api/runs/20260101-000000/regenerate", json={"scene_index": 0})
    assert r.status_code == 202 and r.json()["regenerating"] is True  # allowed on a completed run


# ── thumbnail generation ───────────────────────────────────────────────────────
def test_thumbnail_available_when_run_has_images(client):
    # the fixture run has img_0.png → a thumbnail can be generated for it
    assert client.get("/api/runs/20260101-000000").json()["thumbnail"]["available"] is True


def test_thumbnail_spawns_with_text_and_provider(client, monkeypatch):
    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    r = client.post("/api/runs/20260101-000000/thumbnail", json={"text": "WHY WE SLEEP"})
    assert r.status_code == 202 and r.json()["generating_thumbnail"] is True
    cmd = captured["cmd"]
    assert "--thumbnail" in cmd
    assert cmd[cmd.index("--thumb-text") + 1] == "WHY WE SLEEP"
    assert cmd[cmd.index("--images") + 1] == "placeholder"  # the run's provider, reconstructed


def test_regenerate_forwards_an_edited_prompt(client, monkeypatch):
    run = dash.RUNS_DIR / "20260101-000000"
    _mark_pending_approval(run, images_provider="agnes")

    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    r = client.post(
        "/api/runs/20260101-000000/regenerate",
        json={"scene_index": 1, "prompt": "a calm figure gazing at the stars"},
    )
    assert r.status_code == 202
    cmd = captured["cmd"]
    assert cmd[cmd.index("--prompt") + 1] == "a calm figure gazing at the stars"


def test_delete_run_removes_it(client, tmp_path):
    assert client.get("/api/runs/20260101-000000").status_code == 200
    r = client.request("DELETE", "/api/runs/20260101-000000")
    assert r.status_code == 200 and r.json()["deleted"] == "20260101-000000"
    assert client.get("/api/runs/20260101-000000").status_code == 404  # gone


def test_delete_missing_run_is_404(client):
    assert client.request("DELETE", "/api/runs/nope").status_code == 404


def test_delete_traversal_blocked(client):
    assert client.request("DELETE", "/api/runs/..%2f..%2fetc").status_code == 404


# ── re-edit (reassemble: fresh Cartesia TTS + retimed cuts, reusing images) ─────
def test_reedit_unavailable_without_storyboard(client):
    # The fixture run has img_0.png but no storyboard.json → cannot be re-edited.
    reedit = client.get("/api/runs/20260101-000000").json()["reedit"]
    assert reedit["available"] is False and reedit["video"] is None


def test_reedit_rejected_without_storyboard(client):
    r = client.post("/api/runs/20260101-000000/reassemble", json={"speed": 0.9})
    assert r.status_code == 400


def test_reedit_triggers_and_locks(client, tmp_path, monkeypatch):
    run = dash.RUNS_DIR / "20260101-000000"
    (run / "storyboard.json").write_text('{"title": "t", "style": "s", "scenes": []}')

    class FakeProc:
        def __init__(self):
            self.done = False

        def poll(self):
            return None if not self.done else 0

    created: list[FakeProc] = []

    def fake_popen(*a, **k):
        p = FakeProc()
        created.append(p)
        return p

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)

    r = client.post("/api/runs/20260101-000000/reassemble", json={"speed": 2.0})
    assert r.status_code == 202
    assert r.json()["reassembling"] is True and r.json()["speed"] == 1.5  # clamped to [0.6, 1.5]

    # While it runs, the run reports re-editing and a second trigger is refused.
    assert client.get("/api/runs/20260101-000000").json()["reedit"]["running"] is True
    assert client.post("/api/runs/20260101-000000/reassemble", json={}).status_code == 409

    created[0].done = True  # finished → allowed again
    assert client.post("/api/runs/20260101-000000/reassemble", json={}).status_code == 202


def test_reedit_reports_existing_v2_video(client):
    (dash.RUNS_DIR / "20260101-000000" / "storyboard.json").write_text('{"scenes": []}')
    (dash.RUNS_DIR / "20260101-000000" / "video_v2.mp4").write_bytes(b"fake-v2")
    reedit = client.get("/api/runs/20260101-000000").json()["reedit"]
    assert reedit["available"] is True and reedit["video"] == "video_v2.mp4"


# ── resume (pick up a stopped/failed run, reusing frames on disk) ──────────────
def _mark_failed_with_storyboard(run_dir, images_provider="gemini/agnes"):
    m = json.loads((run_dir / "run.json").read_text())
    m["status"] = "failed"
    m["images_provider"] = images_provider
    m["voice_provider"] = "cartesia"
    (run_dir / "run.json").write_text(json.dumps(m))
    (run_dir / "storyboard.json").write_text('{"title": "t", "scenes": []}')


def test_resume_unavailable_when_completed(client):
    # The fixture run is completed → not resumable.
    assert client.get("/api/runs/20260101-000000").json()["resume"]["available"] is False


def test_resume_rejected_without_storyboard(client):
    m = json.loads((dash.RUNS_DIR / "20260101-000000" / "run.json").read_text())
    m["status"] = "failed"
    (dash.RUNS_DIR / "20260101-000000" / "run.json").write_text(json.dumps(m))
    assert client.post("/api/runs/20260101-000000/resume", json={}).status_code == 400


def test_resume_reconstructs_providers_and_flags(client, monkeypatch):
    run = dash.RUNS_DIR / "20260101-000000"
    _mark_failed_with_storyboard(run, images_provider="gemini/agnes")
    assert client.get("/api/runs/20260101-000000").json()["resume"]["available"] is True

    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    r = client.post("/api/runs/20260101-000000/resume", json={"captions": False})
    assert r.status_code == 202 and r.json()["resuming"] is True
    cmd = captured["cmd"]
    assert "--resume" in cmd and "--no-captions" in cmd
    assert cmd[cmd.index("--char-model") + 1] == "gemini"
    assert cmd[cmd.index("--concept-model") + 1] == "agnes"
    assert cmd[cmd.index("--fallback") + 1] == "agnes"  # different reliable model than gemini char
    assert cmd[cmd.index("--voice") + 1] == "cartesia"


def test_resume_defaults_captions_from_manifest_settings_when_omitted(client, monkeypatch):
    """Resume without an explicit `captions` in the request body must fall back to the ORIGINAL
    run's recorded settings, not a hardcoded True — the gap task 1.2 closes."""
    run = dash.RUNS_DIR / "20260101-000000"
    _mark_failed_with_storyboard(run, images_provider="gemini/agnes")
    m = json.loads((run / "run.json").read_text())
    m["settings"] = {"captions": False}
    (run / "run.json").write_text(json.dumps(m))

    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    r = client.post("/api/runs/20260101-000000/resume", json={})
    assert r.status_code == 202
    assert "--no-captions" in captured["cmd"]


def test_resume_explicit_captions_overrides_manifest_settings(client, monkeypatch):
    """An explicit `captions` in the resume request still wins over the manifest's settings."""
    run = dash.RUNS_DIR / "20260101-000000"
    _mark_failed_with_storyboard(run, images_provider="gemini/agnes")
    m = json.loads((run / "run.json").read_text())
    m["settings"] = {"captions": False}
    (run / "run.json").write_text(json.dumps(m))

    captured: dict = {}

    class FakeProc:
        def poll(self):
            return None

    def fake_popen(cmd, *a, **k):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(dash.subprocess, "Popen", fake_popen)
    r = client.post("/api/runs/20260101-000000/resume", json={"captions": True})
    assert r.status_code == 202
    assert "--no-captions" not in captured["cmd"]


# ── settings persistence (dashboard is the consumer of RunSettings/RunStats) ───
def test_trigger_run_persists_settings_onto_manifest(client, monkeypatch):
    """_spawn_run must write the operator's choices onto the new run's manifest at start, so a
    later re-run/resume of THIS run can recover them (task 1.2)."""

    class FakeProc:
        def poll(self):
            return None

    monkeypatch.setattr(dash.subprocess, "Popen", lambda *a, **k: FakeProc())
    r = client.post("/api/runs", json={"images": "agnes", "voice": "cartesia", "captions": False})
    assert r.status_code == 201
    run_id = r.json()["run_id"]
    manifest = json.loads((dash.RUNS_DIR / run_id / "run.json").read_text())
    assert manifest["settings"]["captions"] is False
    assert manifest["settings"]["images_provider"] == "agnes"
    assert manifest["settings"]["voice"] == "cartesia"
