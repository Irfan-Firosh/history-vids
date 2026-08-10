"""A canned demo storyboard for the Tier-0 PoC (deterministic, offline).

Mirrors Axen's winning structure (result/axen/report.md §3): immersive 2nd-person hook → scale
reframe → authority evidence → emotional turn → existential payoff. In production this object is
produced by an `LLMScriptProvider` (core.llm); here it's hardcoded so the PoC runs offline.
"""

from __future__ import annotations

import sys

from studio.research import strip_citation_markers
from studio.style import LOCKED_STYLE
from studio.types import SHOT_TYPES, Scene, Storyboard

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


#: Framing names the script LLM sometimes puts in ``shot_type`` by mistake, mapped to the shot type
#: each one implies. The two fields are different axes -- ``shot_type`` decides whether people may
#: appear, ``framing`` decides where the camera is -- but both answer "what kind of shot is this?",
#: and a model asked for both inside one object will occasionally cross them. A real run died on
#: ``shot_type: "detail"`` after paying for research, a script, a repair pass and a callout pass.
_FRAMING_AS_SHOT_TYPE: dict[str, str] = {
    "close_up": "character",
    "medium": "character",
    "over_shoulder": "character",
    "profile": "character",
    "establishing": "wide",
    "detail": "concept",
    "cutaway": "concept",
}


def _shot_type_and_framing(raw_shot: object, raw_framing: object) -> tuple[str, str]:
    """Normalise the two shot fields together, recovering when the model crosses them.

    Never raises. ``shot_type`` feeds a pydantic ``Literal`` and was the ONLY field here that could
    abort a run on one bad token -- every other field already degraded to a safe default. A
    storyboard is model output; one stray word must not cost the paid passes that produced it.
    """
    shot = str(raw_shot or "").strip().lower()
    framing = str(raw_framing or "").strip().lower()
    if shot in SHOT_TYPES:
        return shot, framing
    if shot in _FRAMING_AS_SHOT_TYPE:
        # A framing landed in shot_type. Take the shot type it implies, and keep the word as the
        # framing when that slot is empty -- the model told us something, just in the wrong box.
        return _FRAMING_AS_SHOT_TYPE[shot], framing or shot
    return "character", framing


def storyboard_from_dict(data: dict, default_style: str = LOCKED_STYLE) -> Storyboard:
    """Build a validated `Storyboard` from an LLM's JSON (see `studio.llm.parse_json_block`).

    Expects ``{"title": str, "scenes": [{"narration", "image_prompt", "shot_type"?}, ...]}``.

    The local model occasionally emits a *partial* beat (e.g. missing ``image_prompt`` or
    ``narration``) — one such beat used to `KeyError` and abort the whole run. Instead we DROP any
    beat that isn't a dict with both required fields (a beat with no image can't be rendered and one
    with no narration has no audio), keep the rest, and warn to stderr so the data-quality dip is
    visible rather than silent. If nothing usable survives we still fail loudly.

    Inline ``[n]`` citation markers are stripped from every narration here, at the last boundary
    before the text becomes audio — the TTS reads whatever it is handed, and storyboards already on
    disk carry markers the model emitted before the writer stripped them. Stripped indices are
    merged into ``cite`` so provenance survives.
    """
    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ValueError("storyboard JSON needs a non-empty 'scenes' list")
    scenes: list[Scene] = []
    dropped = 0
    for s in raw_scenes:  # a legacy "cutaways" key, if present, is simply ignored
        raw_narration = (s.get("narration") or "").strip() if isinstance(s, dict) else ""
        image_prompt = (s.get("image_prompt") or "").strip() if isinstance(s, dict) else ""
        narration, inline_cites = strip_citation_markers(raw_narration)
        if not narration or not image_prompt:  # partial/garbled beat from the LLM → skip it
            dropped += 1
            continue
        cites = tuple(s.get("cite") or ())
        shot_type, framing = _shot_type_and_framing(s.get("shot_type"), s.get("framing"))
        scenes.append(
            Scene(
                narration=narration,
                image_prompt=image_prompt,
                shot_type=shot_type,
                # A request, not a decision: studio.framing.plan_framings validates it against the
                # shot type and overrules it when it would extend a monotonous run.
                framing=framing,
                cite=cites + tuple(n for n in inline_cites if n not in cites),
                emphasis=(s.get("emphasis") or "").strip(),
                intense=bool(s.get("intense", False)),
                motion="static",
            )
        )
    if dropped:
        print(
            f"  ⚠ storyboard: skipped {dropped} malformed beat(s) missing narration/image_prompt "
            f"({len(scenes)} usable)",
            file=sys.stderr,
        )
    if not scenes:
        raise ValueError("storyboard JSON had no usable scenes (need narration + image_prompt)")
    return Storyboard(
        title=(data.get("title") or "(untitled)"),
        style=data.get("style") or default_style,
        scenes=tuple(scenes),
    )
