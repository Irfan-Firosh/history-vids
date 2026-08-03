from studio.subtitles import ass_timestamp, build_ass


def test_timestamp_format_is_h_mm_ss_cc():
    assert ass_timestamp(0.0) == "0:00:00.00"
    assert ass_timestamp(61.5) == "0:01:01.50"
    assert ass_timestamp(3661.25) == "1:01:01.25"


def test_every_cue_becomes_one_dialogue_line():
    cues = [("hello there", 0.0, 1.0), ("second cue", 1.0, 2.0)]
    out = build_ass(cues)
    assert out.count("\nDialogue:") == 2
    assert "hello there" in out and "second cue" in out


def test_braces_and_newlines_are_escaped_so_they_cannot_inject_ass_override_tags():
    # `{...}` is an ASS override block. Unescaped, narration containing braces would be
    # interpreted as styling commands instead of shown as text.
    out = build_ass([("a {b} c\nd", 0.0, 1.0)])
    assert "{b}" not in out
    assert "\\N" in out


def test_header_declares_the_render_resolution():
    out = build_ass([("x", 0.0, 1.0)], width=1920, height=1080)
    assert "PlayResX: 1920" in out
    assert "PlayResY: 1080" in out


def test_commas_in_cue_text_do_not_shift_dialogue_fields():
    # A Dialogue line has 9 comma-separated fields (Layer..Effect) before the free-form Text
    # field. Commas inside narration must reach the Text field intact, not get stripped/escaped
    # or split into extra fields.
    out = build_ass([("wait, no, actually yes", 0.0, 1.0)])
    line = next(line for line in out.splitlines() if line.startswith("Dialogue:"))
    fields = line.split(",", 9)
    assert len(fields) == 10
    assert fields[9] == "wait, no, actually yes"
