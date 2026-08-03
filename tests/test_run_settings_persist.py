"""The subprocess entry points must persist RunSettings onto the manifest themselves.

Task 1.2 taught `dashboard/app.py::_spawn_run` to write `RunSettings` onto the manifest before
spawning the pipeline subprocess. But that subprocess — `tools/studio_poc.py::main` or
`tools/run_pipeline.py::main` — calls `RunRecorder.create()` again with the same run_id, which
unconditionally builds a fresh manifest (default `RunSettings()`), overwriting whatever the
dashboard just wrote. A real (non-mocked) run therefore still records `captions=True` regardless of
what the operator actually chose.

These tests call the real subprocess entry points directly (not through a mocked
`subprocess.Popen`, which is exactly what let this gap slip past the task 1.2 test suite) and read
the persisted `run.json` back off disk.
"""

from __future__ import annotations

import json
import sys

from tools import run_pipeline as rp
from tools import studio_poc as sp


def test_studio_poc_main_persists_operator_choices_onto_manifest(monkeypatch, tmp_path):
    """`tools/studio_poc.py:main` is the canned-demo / no-topic subprocess entry point. It must
    call `rec.set_settings(...)` with the parsed args, not leave the manifest on `RunSettings()`
    defaults, so a later rerun/resume of a REAL run recovers the operator's actual choice."""
    monkeypatch.setattr(sp, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(sp, "render_storyboard", lambda *a, **kw: None)
    # main() calls load_dotenv() first; with no .env in this worktree, python-dotenv's find_dotenv()
    # walks up and would load the shared checkout's real .env (real secrets) into this test process
    # for the rest of the pytest session. Irrelevant to what's under test here — stub it out.
    monkeypatch.setattr(sp, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setattr(
        sys, "argv",
        [
            "studio_poc.py", "--no-captions", "--images", "agnes", "--voice", "cartesia",
            "--run-id", "r1",
        ],
    )

    sp.main()

    manifest = json.loads((tmp_path / "r1" / "run.json").read_text())
    assert manifest["settings"]["captions"] is False
    assert manifest["settings"]["images_provider"] == "agnes"
    assert manifest["settings"]["voice"] == "cartesia"


def test_run_pipeline_main_persists_operator_choices_onto_manifest(monkeypatch, tmp_path):
    """`tools/run_pipeline.py:main` is the whole-pipeline (topic) subprocess entry point. Same gap
    as studio_poc.py: it must call `rec.set_settings(...)` itself."""
    out_dir = tmp_path / "script_out"
    out_dir.mkdir()
    (out_dir / "storyboard.json").write_text(json.dumps({
        "title": "t",
        "scenes": [{"narration": "beat zero", "image_prompt": "p", "shot_type": "character"}],
    }))

    monkeypatch.setattr(rp, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(rp, "build_and_save", lambda *a, **kw: out_dir)
    monkeypatch.setattr(rp, "render_storyboard", lambda *a, **kw: None)
    # See the same load_dotenv() note in the studio_poc test above.
    monkeypatch.setattr(rp, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setattr(
        sys, "argv",
        [
            "run_pipeline.py", "--topic", "T", "--no-captions",
            "--min-minutes", "3", "--max-minutes", "5",
            "--images", "agnes", "--voice", "cartesia", "--run-id", "r2",
        ],
    )

    rp.main()

    manifest = json.loads((tmp_path / "r2" / "run.json").read_text())
    assert manifest["settings"]["captions"] is False
    assert manifest["settings"]["min_minutes"] == 3.0
    assert manifest["settings"]["max_minutes"] == 5.0
    assert manifest["settings"]["images_provider"] == "agnes"
    assert manifest["settings"]["voice"] == "cartesia"
