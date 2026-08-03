from studio.script_prompt import SCRIPT_SYSTEM_PROMPT, build_repair_user_prompt


def test_hook_rule_demands_an_actual_question_mark():
    # 7 of 13 generated scripts contained no question mark at all, because "hook" reads to a
    # model as "engaging opener", not "ask something". The rule must be literal.
    #
    # Do NOT assert on "question mark" alone: the prompt ALREADY contains that phrase, in the
    # image-prompt guidance ("a giant question mark" as a drawable symbol). Verified 2026-08-03 —
    # that assertion passes today and would make this test vacuous. Assert on the hook rule.
    assert "FIRST beat must contain a literal question mark" in SCRIPT_SYSTEM_PROMPT


def test_rhythm_rule_replaces_the_uniform_sentence_rule():
    # The old rule ("2-3 full sentences", "a one-sentence beat is too short") forced uniform
    # 10-17 word sentences and made the >=25% short-sentence floor unreachable.
    assert "one-sentence beat is too short" not in SCRIPT_SYSTEM_PROMPT
    assert "under 8 words" in SCRIPT_SYSTEM_PROMPT


def test_stale_held_shot_model_is_gone_and_clauses_are_explained():
    # plan_shots subdivides beats at clause boundaries into ~2.2s shots; the old prompt told the
    # model a beat was one held shot for 8-16 seconds, which stopped being true.
    assert "8-12 seconds" not in SCRIPT_SYSTEM_PROMPT
    assert "clause" in SCRIPT_SYSTEM_PROMPT.lower()


def test_specificity_rule_targets_abstract_topics():
    # numbers_per_1k measured 0.0 on abstract topics whose briefs carried 1000-1942 digits.
    assert "abstract" in SCRIPT_SYSTEM_PROMPT.lower()


def test_repair_prompt_embeds_the_draft_and_every_failure_verbatim():
    draft = '{"title": "T", "scenes": [{"narration": "A long flat line.", "cite": []}]}'
    failures = ("no question mark anywhere — the hook never asks anything",
                "mean sentence 30.0w (max 15.0)")
    out = build_repair_user_prompt(draft, failures)
    assert draft in out
    for f in failures:
        assert f in out, f"failure not passed through: {f}"


def test_repair_prompt_protects_beat_count_and_citations():
    # A repair that drops beats changes the image count, and one that drops cite indices breaks
    # the grounding gate that already passed. Both must survive the revision.
    out = build_repair_user_prompt("{}", ["mean sentence 30.0w (max 15.0)"])
    assert "same number of beats" in out.lower()
    assert "cite" in out
