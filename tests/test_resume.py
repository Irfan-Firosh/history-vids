"""Resume must reuse frames already on disk — never delete or regenerate them."""

from __future__ import annotations

from studio import Scene, Storyboard
from tools import studio_poc as sp


class _FakeProvider:
    """Records which frames it was asked to generate."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[str] = []

    def generate(self, prompt, out_path, refs=()):
        self.calls.append(out_path.name)
        out_path.write_bytes(b"freshly-generated")
        return out_path


class _FakeVoice:
    name = "say"


def _fake_render_video(segs, wav, cues, out, overlays=None):
    out.write_bytes(b"vid")


def test_resume_reuses_existing_frames_and_generates_only_missing(tmp_path, monkeypatch):
    char, concept = _FakeProvider("gemini"), _FakeProvider("gemini")
    providers = sp.ImageProviders(char, concept)

    # Stub the heavy bits: narration (2 beats, ≥8s each → 1 frame each), assembly, probe.
    def fake_narration(scenes, voice, out_dir):
        return out_dir / "n.wav", [(0.0, 9.0), (9.0, 18.0)], [], [], []

    monkeypatch.setattr(sp, "build_narration", fake_narration)
    monkeypatch.setattr(sp, "render_video", _fake_render_video)
    monkeypatch.setattr(sp, "ffprobe_duration", lambda p: 18.0)
    monkeypatch.setattr(sp, "load_channel_refs", lambda: [])

    sb = Storyboard(title="t", style="s", scenes=(
        Scene(narration="beat zero", image_prompt="p", shot_type="character"),
        Scene(narration="beat one", image_prompt="q", shot_type="map"),
    ))
    rec = sp.RunRecorder.create(
        tmp_path, title="t", images_provider="gemini",
        voice_provider="say", scene_count=2, run_id="r",
    )
    (rec.dir / "img_0.png").write_bytes(b"ALREADY-DONE")  # a frame from the interrupted run

    sp.render_storyboard(rec, sb, providers, _FakeVoice(), captions=False, resume=True)

    # img_0 existed → skipped + byte-preserved; img_1 was missing → generated.
    assert "img_0.png" not in char.calls
    assert (rec.dir / "img_0.png").read_bytes() == b"ALREADY-DONE"
    assert "img_1.png" in concept.calls
    assert (rec.dir / "video.mp4").is_file()
    # The run log states the consistency mode plainly (this provider sends no reference image).
    assert "character consistency: prompt-only" in (rec.dir / "log.txt").read_text()


def test_no_resume_regenerates_everything(tmp_path, monkeypatch):
    char, concept = _FakeProvider("gemini"), _FakeProvider("gemini")
    monkeypatch.setattr(
        sp, "build_narration",
        lambda scenes, voice, out_dir: (out_dir / "n.wav", [(0.0, 9.0)], [], [], []),
    )
    monkeypatch.setattr(sp, "render_video", _fake_render_video)
    monkeypatch.setattr(sp, "ffprobe_duration", lambda p: 9.0)
    monkeypatch.setattr(sp, "load_channel_refs", lambda: [])

    sb = Storyboard(title="t", style="s", scenes=(
        Scene(narration="only beat", image_prompt="p", shot_type="character"),
    ))
    rec = sp.RunRecorder.create(
        tmp_path, title="t", images_provider="gemini",
        voice_provider="say", scene_count=1, run_id="r",
    )
    (rec.dir / "img_0.png").write_bytes(b"OLD")
    sp.render_storyboard(rec, sb, sp.ImageProviders(char, concept), _FakeVoice(), captions=False)
    assert "img_0.png" in char.calls  # without resume, it regenerates


def test_resume_reuses_saved_narration_and_records_progress(tmp_path, monkeypatch):
    # narration.wav + beat_spans.json already exist → resume must NOT re-synthesize (no TTS/drift).
    calls = {"narration": 0}

    def counting_narration(scenes, voice, out_dir):
        calls["narration"] += 1
        return out_dir / "narration.wav", [(0.0, 9.0), (9.0, 18.0)]

    monkeypatch.setattr(sp, "build_narration", counting_narration)
    monkeypatch.setattr(sp, "render_video", _fake_render_video)
    monkeypatch.setattr(sp, "ffprobe_duration", lambda p: 18.0)
    monkeypatch.setattr(sp, "load_channel_refs", lambda: [])

    sb = Storyboard(title="t", style="s", scenes=(
        Scene(narration="beat zero", image_prompt="p", shot_type="character"),
        Scene(narration="beat one", image_prompt="q", shot_type="map"),
    ))
    char, concept = _FakeProvider("gemini"), _FakeProvider("gemini")
    rec = sp.RunRecorder.create(
        tmp_path, title="t", images_provider="gemini",
        voice_provider="cartesia", scene_count=2, run_id="r",
    )
    # Pre-seed a completed narration + spans + first frame from the interrupted run.
    (rec.dir / "narration.wav").write_bytes(b"WAV")
    sp._save_beat_spans(rec.dir, [(0.0, 9.0), (9.0, 18.0)])
    (rec.dir / "img_0.png").write_bytes(b"DONE")

    sp.render_storyboard(rec, sb, sp.ImageProviders(char, concept), _FakeVoice(),
                         captions=False, resume=True)

    assert calls["narration"] == 0  # reused saved narration.wav + spans, no re-synth
    assert "img_1.png" in concept.calls  # only the missing frame generated
    assert rec.manifest.resume_note and "1/2" in rec.manifest.resume_note  # truthful progress


def test_ref_capability_is_read_per_instance_not_per_provider_name(monkeypatch):
    """Agnes only sends a reference image when AGNES_IMG2IMG=1, so ref-capability must come from
    the instance. A name-based check claimed ref-conditioned consistency for the default Agnes
    setup and told the user to generate ref sheets it would never use."""
    monkeypatch.delenv("AGNES_IMG2IMG", raising=False)
    assert sp.wants_refs(sp.AgnesImageProvider()) is False  # default: text-to-image, refs ignored

    monkeypatch.setenv("AGNES_IMG2IMG", "1")
    assert sp.wants_refs(sp.AgnesImageProvider()) is True  # opted in → image-to-image

    assert sp.wants_refs(sp.GeminiImageProvider()) is True
    assert sp.wants_refs(sp.HuggingFaceImageProvider()) is False
    assert sp.wants_refs(sp.PlaceholderImageProvider()) is False
    assert sp.wants_refs(_FakeProvider("anything")) is False  # duck-typed → no claim of refs
