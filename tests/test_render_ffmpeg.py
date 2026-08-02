from tools.render import ffmpeg


def test_ffmpeg_bin_defaults_to_path_lookup(monkeypatch):
    monkeypatch.delenv("FFMPEG_BIN", raising=False)
    assert ffmpeg.ffmpeg_bin() == "ffmpeg"


def test_ffmpeg_bin_honours_env(monkeypatch):
    monkeypatch.setenv("FFMPEG_BIN", "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
    assert ffmpeg.ffmpeg_bin() == "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"


def test_has_filter_reports_a_filter_that_always_exists():
    # `overlay` ships in every ffmpeg build; if this fails, ffmpeg itself is broken.
    assert ffmpeg.has_filter("overlay") is True


def test_has_filter_reports_false_for_a_nonexistent_filter():
    assert ffmpeg.has_filter("definitely_not_a_real_filter") is False


def test_subtitle_backend_is_one_of_the_two_known_values():
    assert ffmpeg.subtitle_backend() in {"libass", "png_overlay"}
