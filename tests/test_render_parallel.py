"""render_storyboard's image loop must actually run frame generation concurrently.

The whole point of Task 6.1 is to stop paying ~200 x 3s of Agnes latency serially. A fake provider
that sleeps briefly proves real overlap: several independent scenes must finish in close to ONE
sleep interval — not N of them — when routed through the `ThreadPoolExecutor(max_workers=6)` in
`tools.studio_poc.render_storyboard`, instead of silently falling back to a serial loop.
"""

from __future__ import annotations

import threading
import time

from studio import Scene, Storyboard
from tools import studio_poc as sp


class _SlowFakeProvider:
    """Sleeps briefly per frame — long enough that serial generation is easy to detect in a wall-
    clock assertion, short enough the whole test stays fast even if it (bug) runs serially."""

    name = "slow-fake"

    def __init__(self, delay: float) -> None:
        self.delay = delay

    def generate(self, prompt, out_path, refs=()):
        time.sleep(self.delay)
        out_path.write_bytes(b"frame")
        return out_path


def _fake_render_segment(image, duration, out_dir, *, width=1920, height=1080, fps=30):
    """Stand-in for `tools.render.segments.render_segment` — no real ffmpeg needed for this test."""
    out_dir.mkdir(parents=True, exist_ok=True)
    seg = out_dir / f"seg_{image.stem}.mp4"
    seg.write_bytes(b"seg")
    return seg, False


def _fake_assemble(segments, wav, cues, out, *, work_dir, width=1920, height=1080, fps=30):
    """Stand-in for `tools.render.assemble.assemble`."""
    out.write_bytes(b"vid")
    return out


class _FakeVoice:
    name = "say"


def test_render_storyboard_generates_frames_concurrently(tmp_path, monkeypatch):
    n_scenes = 6
    delay = 0.3
    provider = _SlowFakeProvider(delay)
    providers = sp.ImageProviders(provider, provider)

    def fake_narration(scenes, voice, out_dir):
        spans = [(9.0 * i, 9.0 * (i + 1)) for i in range(n_scenes)]  # 9s/beat → 1 frame each
        return out_dir / "n.wav", spans, [], [], []

    monkeypatch.setattr(sp, "build_narration", fake_narration)
    monkeypatch.setattr(sp, "render_segment", _fake_render_segment)
    monkeypatch.setattr(sp, "assemble", _fake_assemble)
    monkeypatch.setattr(sp, "ffprobe_duration", lambda p: 9.0 * n_scenes)
    monkeypatch.setattr(sp, "load_channel_refs", lambda: [])

    sb = Storyboard(title="t", style="s", scenes=tuple(
        Scene(narration=f"beat {i}", image_prompt="p", shot_type="map") for i in range(n_scenes)
    ))
    rec = sp.RunRecorder.create(
        tmp_path, title="t", images_provider="slow-fake", voice_provider="say",
        scene_count=n_scenes, run_id="r",
    )

    started = time.monotonic()
    sp.render_storyboard(rec, sb, providers, _FakeVoice(), captions=False, skip_style_check=True)
    elapsed = time.monotonic() - started

    # Serial generation of n_scenes independent frames would take ~n_scenes * delay. With
    # max_workers=6 >= n_scenes, all of them should overlap almost entirely, taking close to ONE
    # delay plus bookkeeping — a generous fraction of the fully-serial time proves real overlap
    # without making the assertion flaky under CI scheduling jitter.
    assert elapsed < n_scenes * delay * 0.6

    # And correctness wasn't sacrificed for speed: every scene still got its own frame + segment.
    for i in range(n_scenes):
        assert (rec.dir / f"img_{i}.png").read_bytes() == b"frame"
    assert rec.manifest.status == "completed"


def test_generate_frame_serialises_fallback_log_writes_with_shared_lock(tmp_path):
    """`_generate_frame` now runs inside a shared `ThreadPoolExecutor` (render_storyboard's image
    loop); `RunRecorder.log` (studio/run_log.py) appends to log.txt with NO locking of its own, so
    several frames hitting their fallback path at the same instant could interleave their writes
    into one corrupted line. Proves the caller-supplied `log_lock` genuinely serialises those calls
    — deterministically, via a sleeping fake logger that records (enter, exit) timestamps, rather
    than racing on file-write atomicity (which would likely pass even with NO lock at all on most
    platforms for strings this short, proving nothing)."""
    intervals: list[tuple[float, float]] = []
    intervals_lock = threading.Lock()

    class _FailingProvider:
        name = "primary"

        def generate(self, prompt, out_path, refs=()):
            raise RuntimeError("boom")

    class _FallbackProvider:
        name = "fallback"

        def generate(self, prompt, out_path, refs=()):
            out_path.write_bytes(b"ok")
            return out_path

    class _FakeRec:
        def log(self, msg: str) -> None:
            start = time.monotonic()
            time.sleep(0.05)  # long enough that two un-serialised calls would visibly overlap
            with intervals_lock:
                intervals.append((start, time.monotonic()))

    log_lock = threading.Lock()
    primary, fallback = _FailingProvider(), _FallbackProvider()
    rec = _FakeRec()

    threads = [
        threading.Thread(
            target=sp._generate_frame,
            args=(primary, "p", tmp_path / f"img_{i}.png", (), fallback, rec, i, 0, log_lock),
        )
        for i in range(6)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(intervals) == 6
    intervals.sort()
    for (_, end), (next_start, _) in zip(intervals, intervals[1:], strict=False):
        assert next_start >= end  # no two log() calls ever overlapped in time
