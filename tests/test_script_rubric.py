from studio.script_rubric import (
    MAX_FIRST_QUESTION_SEC,
    RubricReport,
    score_script,
)


def test_question_mark_followed_by_a_closing_quote_is_still_a_question():
    # Mack's 1.6M-view hook ends `?"`. Naive detection missed it and reported the first question
    # at 313s instead of 23s — which would fail the single most important rule on a winning script.
    narrations = ['He asked one thing: "what if we were never meant to survive?" Nobody answered.']
    report = score_script(narrations)
    assert report.first_question_sec is not None
    assert report.first_question_sec < MAX_FIRST_QUESTION_SEC


def test_a_script_with_no_question_at_all_reports_none_and_fails():
    report = score_script(["This is a statement. So is this. And this one too."])
    assert report.first_question_sec is None
    assert not report.ok
    assert any("question" in f for f in report.failures)


def test_first_question_time_is_derived_from_word_position_and_wpm():
    # 98 words of preamble at 196 wpm = 30s, so the question lands at ~30s.
    narrations = [" ".join(["word"] * 98) + " why did they leave?"]
    report = score_script(narrations, wpm=196.0)
    assert 29.0 <= report.first_question_sec <= 31.5


def test_second_person_density_is_measured_after_the_90_second_mark():
    # score_script locates "after 90s" by word position (word 294 at 196 wpm), not by treating the
    # whole narration as already-past-90s content — so a 294-word preamble is required before the
    # body, or the "you" mentions never cross the cutoff. 282 words of body (6 x 47, joined with
    # spaces so the repeats don't glue together) containing 6 "you" -> ~21/1k, comfortably passing.
    preamble = " ".join(["intro"] * 294)
    segment = " ".join(["filler"] * 44) + " you know this."
    body = " ".join([segment] * 6)
    report = score_script([preamble + " " + body])
    assert report.second_person_after_90s_per_1k >= 8.0


def test_long_rambling_sentences_fail_the_rubric():
    # The 24K underperformer: mean sentence 28.4 words, 2.4% short, 51% long.
    long_sentence = " ".join(["word"] * 30) + "."
    report = score_script([long_sentence * 10])
    assert not report.ok
    assert any("sentence" in f for f in report.failures)


def test_summary_is_a_single_readable_line():
    report = score_script(["Why did they leave? You know. They ran. It was 1905."])
    assert "\n" not in report.summary()
    assert isinstance(report, RubricReport)
