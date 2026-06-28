"""A canned demo storyboard for the Tier-0 PoC (deterministic, offline).

Mirrors Axen's winning structure (result/axen/report.md §3): immersive 2nd-person hook → scale
reframe → authority evidence → emotional turn → existential payoff. In production this object is
produced by an `LLMScriptProvider` (core.llm); here it's hardcoded so the PoC runs offline.
"""

from __future__ import annotations


from studio.style import LOCKED_STYLE
from studio.types import Scene, Storyboard

_BEATS = [
    # (narration, image_prompt, shot_type, emphasis). Locked style appended at render; shot_type
    # drives reference conditioning. Images stay TEXT-FREE — a pivotal number/date/name goes in
    # `emphasis` (a post overlay placed on the image's whitespace), never drawn by the model.
    (
        "You wake up when your body is ready. No alarm, no schedule, no place you need to be.",
        "a person with a calm, content, relaxed expression, stretching as they wake at dawn inside "
        "a simple cave",
        "character",
        "",
    ),
    (
        "For ninety-nine percent of human history, this was every single morning.",
        "a small group of hunter-gatherers with calm neutral faces around a simple campfire on a "
        "grassy plain at sunrise",
        "wide",
        "",
    ),
    (
        "Studies of modern foragers show just fifteen to twenty hours a week securing food.",
        "a person with a focused expression gathering berries on a grassy plain",
        "character",
        "15 hrs/week",
    ),
    (
        "The rest of the time they rested, told stories, and made art, because they had time.",
        "people sitting around a campfire at night, smiling and laughing happily, telling stories, "
        "simple cave paintings on the wall behind them",
        "wide",
        "",
    ),
    (
        "They woke up every morning already free. Already enough. With nothing to prove to anyone.",
        "a lone person with a peaceful, serene little smile, standing on a hill at night looking "
        "up at a big starry sky",
        "character",
        "",
    ),
]

DEMO_STORYBOARD = Storyboard(
    title="What Did Ancient Humans Do All Day?",
    style=LOCKED_STYLE,
    # Static hard cuts (the chosen style): each image held for its narration beat, no motion.
    scenes=tuple(
        Scene(narration=n, image_prompt=p, motion="static", shot_type=st, emphasis=em)
        for n, p, st, em in _BEATS
    ),
)
