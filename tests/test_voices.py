"""Narrator voice resolution — the order that decides which voice a paid TTS call uses."""

from __future__ import annotations

import pytest

from studio.voices import NARRATOR, VOICES, resolve_voice


def test_default_is_the_curious_narrator():
    assert resolve_voice() == VOICES["curious"]
    assert NARRATOR == "curious"


def test_explicit_id_wins_over_a_name():
    assert resolve_voice("custom-clone-id", "angry") == "custom-clone-id"


def test_name_selects_the_emotional_take():
    for name, vid in VOICES.items():
        assert resolve_voice(None, name) == vid


def test_name_is_case_and_space_insensitive():
    assert resolve_voice(None, "  Angry ") == VOICES["angry"]


def test_unknown_name_raises_rather_than_narrating_in_the_wrong_voice():
    with pytest.raises(ValueError, match="unknown CARTESIA_VOICE"):
        resolve_voice(None, "sarcastic")


def test_all_four_takes_are_distinct_ids():
    assert len(set(VOICES.values())) == len(VOICES) == 4
