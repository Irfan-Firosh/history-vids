from pathlib import Path

from PIL import Image

from tools.render.segments import CACHE_VERSION, render_segment, segment_key


def _make_image(path: Path, color: tuple[int, int, int] = (200, 30, 30)) -> Path:
    """A tiny synthetic still — no downloads, no real assets, encodes in milliseconds."""
    Image.new("RGB", (64, 36), color=color).save(path)
    return path


def test_key_changes_when_any_input_changes():
    base = segment_key(b"img", 2.0, 1920, 1080, 30)
    assert segment_key(b"different", 2.0, 1920, 1080, 30) != base
    assert segment_key(b"img", 2.5, 1920, 1080, 30) != base
    assert segment_key(b"img", 2.0, 1280, 1080, 30) != base
    assert segment_key(b"img", 2.0, 1920, 720, 30) != base
    assert segment_key(b"img", 2.0, 1920, 1080, 24) != base


def test_key_is_stable_for_identical_inputs():
    assert segment_key(b"img", 2.0, 1920, 1080, 30) == segment_key(b"img", 2.0, 1920, 1080, 30)


def test_key_embeds_the_cache_version_so_a_renderer_change_invalidates_everything():
    # A cache that survives a renderer change silently ships stale frames — the worst failure mode
    # here, because the output looks fine.
    assert str(CACHE_VERSION) in segment_key(b"img", 2.0, 1920, 1080, 30)


def test_render_segment_produces_a_nonempty_file_and_reports_a_cold_render(tmp_path):
    image = _make_image(tmp_path / "shot.png")

    out, was_cached = render_segment(image, 0.2, tmp_path / "out", width=64, height=36, fps=10)

    assert out.exists()
    assert out.stat().st_size > 0
    assert was_cached is False


def test_second_call_with_identical_inputs_is_cached_and_never_touches_ffmpeg(tmp_path):
    image = _make_image(tmp_path / "shot.png")
    out_dir = tmp_path / "out"

    first, first_cached = render_segment(image, 0.2, out_dir, width=64, height=36, fps=10)
    assert first_cached is False
    first_mtime_ns = first.stat().st_mtime_ns
    first_inode = first.stat().st_ino

    second, second_cached = render_segment(image, 0.2, out_dir, width=64, height=36, fps=10)

    assert second == first
    assert second_cached is True
    # A re-encode rewrites the file: new bytes, new mtime. Identical mtime/inode is proof ffmpeg
    # never ran the second time — this is the actual win, not just "a file exists".
    assert second.stat().st_mtime_ns == first_mtime_ns
    assert second.stat().st_ino == first_inode


def test_changing_image_bytes_produces_a_different_path_and_a_real_reencode(tmp_path):
    out_dir = tmp_path / "out"
    image_a = _make_image(tmp_path / "a.png", color=(200, 30, 30))
    image_b = _make_image(tmp_path / "b.png", color=(30, 200, 30))

    out_a, cached_a = render_segment(image_a, 0.2, out_dir, width=64, height=36, fps=10)
    out_b, cached_b = render_segment(image_b, 0.2, out_dir, width=64, height=36, fps=10)

    assert out_a != out_b
    assert cached_a is False
    assert cached_b is False


def test_changing_duration_width_height_or_fps_each_forces_a_distinct_reencoded_path(tmp_path):
    image = _make_image(tmp_path / "shot.png")
    out_dir = tmp_path / "out"

    base, base_cached = render_segment(image, 0.2, out_dir, width=64, height=36, fps=10)
    diff_duration, dur_cached = render_segment(image, 0.4, out_dir, width=64, height=36, fps=10)
    diff_width, w_cached = render_segment(image, 0.2, out_dir, width=48, height=36, fps=10)
    diff_height, h_cached = render_segment(image, 0.2, out_dir, width=64, height=48, fps=10)
    diff_fps, fps_cached = render_segment(image, 0.2, out_dir, width=64, height=36, fps=12)

    variants = [diff_duration, diff_width, diff_height, diff_fps]
    assert base not in variants
    assert len(set(variants)) == 4  # every variant is also distinct from every other variant
    assert not any([base_cached, dur_cached, w_cached, h_cached, fps_cached])
