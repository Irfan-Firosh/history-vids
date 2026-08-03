"""Numeric quality gate for a generated script (pure).

Mirrors ``studio.research.grounding_report``: measure, report, and let the caller refuse BEFORE any
image or TTS spend. Thresholds are derived in context/research/2026-08-01/05-script-craft.md from an
age-controlled cohort — three videos on one channel, same narrator and format, published within
~4 weeks, spanning 996K / 31K / 24K views. Holding channel and age constant is what makes the
measured differences attributable to the writing.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

#: The hook question must land early. Winner: 0:16. Underperformer: 6:51.
MAX_FIRST_QUESTION_SEC = 45.0
#: Second-person density AFTER the hook is what separates winners; the opening always has it.
MIN_2P_AFTER_90S_PER_1K = 8.0
#: Winner 14.0 words; underperformer 28.4.
MAX_MEAN_SENTENCE_WORDS = 17.0
#: Winner 31% of sentences under 8 words; underperformer 2.4%.
MIN_SHORT_SENTENCE_PCT = 25.0
#: Winner 14% over 25 words; underperformer 51%.
MAX_LONG_SENTENCE_PCT = 22.0
#: Concrete figures. Winner 14.8/1k; underperformer 2.6.
MIN_NUMBERS_PER_1K = 10.0

_SHORT_SENTENCE_WORDS = 8
_LONG_SENTENCE_WORDS = 25
_BODY_STARTS_SEC = 90.0

#: A question mark may be followed by a closing quote or bracket before the sentence truly ends.
#: Missing this reads Mack's `?"` hook at 313s instead of 23s.
_QUESTION = re.compile(r'\?["\'”’)\]]*')
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])["\'”’)\]]*\s+')
_SECOND_PERSON = re.compile(r"\b(you|your|yours|yourself)\b", re.IGNORECASE)
_NUMBER = re.compile(r"\b\d[\d,.]*\b")


class RubricReport(BaseModel):
    """How a script measures against the reference cohort."""

    model_config = ConfigDict(frozen=True)

    words: int
    first_question_sec: float | None
    second_person_per_1k: float
    second_person_after_90s_per_1k: float
    mean_sentence_words: float
    short_sentence_pct: float
    long_sentence_pct: float
    numbers_per_1k: float
    failures: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """False when the script violates a threshold the cohort says predicts failure."""
        return not self.failures

    def summary(self) -> str:
        q = f"{self.first_question_sec:.0f}s" if self.first_question_sec is not None else "never"
        return (
            f"{self.words}w · first ? {q} · "
            f"2p {self.second_person_after_90s_per_1k:.1f}/1k after 90s "
            f"· sentence {self.mean_sentence_words:.1f}w "
            f"({self.short_sentence_pct:.0f}% short / {self.long_sentence_pct:.0f}% long) "
            f"· numbers {self.numbers_per_1k:.1f}/1k"
        )


def _sentences(text: str) -> list[str]:
    return [s for s in (p.strip() for p in _SENTENCE_SPLIT.split(text)) if s]


def score_script(narrations: Sequence[str], wpm: float = 196.0) -> RubricReport:
    """Measure a script against the reference thresholds. Pure and free — run before any spend."""
    text = " ".join(n.strip() for n in narrations if n.strip())
    words = text.split()
    n_words = len(words)
    if n_words == 0:
        return RubricReport(
            words=0,
            first_question_sec=None,
            second_person_per_1k=0.0,
            second_person_after_90s_per_1k=0.0,
            mean_sentence_words=0.0,
            short_sentence_pct=0.0,
            long_sentence_pct=0.0,
            numbers_per_1k=0.0,
            failures=("empty script",),
        )
    per_word_sec = 60.0 / wpm if wpm > 0 else 0.0

    match = _QUESTION.search(text)
    first_q: float | None = None
    if match:
        first_q = len(text[: match.start()].split()) * per_word_sec

    body_start_word = int(_BODY_STARTS_SEC / per_word_sec) if per_word_sec else 0
    body = " ".join(words[body_start_word:])
    body_words = max(len(body.split()), 1)

    sents = _sentences(text) or [text]
    lengths = [len(s.split()) for s in sents]
    mean_len = sum(lengths) / len(lengths)
    short_pct = sum(1 for n in lengths if n < _SHORT_SENTENCE_WORDS) / len(lengths) * 100
    long_pct = sum(1 for n in lengths if n > _LONG_SENTENCE_WORDS) / len(lengths) * 100

    per_1k = 1000.0 / n_words
    report = RubricReport(
        words=n_words,
        first_question_sec=first_q,
        second_person_per_1k=len(_SECOND_PERSON.findall(text)) * per_1k,
        second_person_after_90s_per_1k=len(_SECOND_PERSON.findall(body)) * 1000.0 / body_words,
        mean_sentence_words=mean_len,
        short_sentence_pct=short_pct,
        long_sentence_pct=long_pct,
        numbers_per_1k=len(_NUMBER.findall(text)) * per_1k,
    )
    failures: list[str] = []
    if report.first_question_sec is None:
        failures.append("no question mark anywhere — the hook never asks anything")
    elif report.first_question_sec > MAX_FIRST_QUESTION_SEC:
        failures.append(
            f"first question at {report.first_question_sec:.0f}s "
            f"(max {MAX_FIRST_QUESTION_SEC:.0f}s)"
        )
    if report.second_person_after_90s_per_1k < MIN_2P_AFTER_90S_PER_1K:
        failures.append(
            f"second person {report.second_person_after_90s_per_1k:.1f}/1k after 90s "
            f"(min {MIN_2P_AFTER_90S_PER_1K})"
        )
    if report.mean_sentence_words > MAX_MEAN_SENTENCE_WORDS:
        failures.append(
            f"mean sentence {report.mean_sentence_words:.1f}w (max {MAX_MEAN_SENTENCE_WORDS})"
        )
    if report.short_sentence_pct < MIN_SHORT_SENTENCE_PCT:
        failures.append(
            f"only {report.short_sentence_pct:.0f}% short sentences "
            f"(min {MIN_SHORT_SENTENCE_PCT:.0f}%)"
        )
    if report.long_sentence_pct > MAX_LONG_SENTENCE_PCT:
        failures.append(
            f"{report.long_sentence_pct:.0f}% long sentences (max {MAX_LONG_SENTENCE_PCT:.0f}%)"
        )
    if report.numbers_per_1k < MIN_NUMBERS_PER_1K:
        failures.append(f"numbers {report.numbers_per_1k:.1f}/1k (min {MIN_NUMBERS_PER_1K})")
    return report.model_copy(update={"failures": tuple(failures)})
