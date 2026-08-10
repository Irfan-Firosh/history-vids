"""Cartesia narrator voices (pure data) — one speaker, four emotional takes.

Verified against the Cartesia `/voices/{id}` API on 2026-08-09: all four ids below are the SAME
public speaker, "Carson", recorded in four emotional deliveries. That is the property that makes
them usable together — switching between them mid-video changes the *delivery*, not the narrator.
Four unrelated voices would sound like four different people reading one script.

These are public, non-secret ids (`is_public: true`, `is_owner: false`), so they belong in code
rather than `.env`. Only the API key is a secret.

Resolution order used by the Cartesia providers in ``tools/studio_poc.py``:

  1. ``CARTESIA_VOICE_ID`` — an explicit id, wins over everything (custom clones live here)
  2. ``CARTESIA_VOICE``    — a name from :data:`VOICES` (``curious``, ``angry``, …)
  3. :data:`NARRATOR`      — the default

Reading those env vars is the caller's job; this module stays pure.
"""

from __future__ import annotations

#: Carson, by emotional take. Keys are the emotion; values are Cartesia voice ids.
VOICES: dict[str, str] = {
    "curious": "86e30c1d-714b-4074-a1f2-1cb6b552fb49",   # Carson - Curious Conversationalist
    "disgust": "ee8b13e7-98af-4b15-89d1-8d402be10c94",   # Carson - Disgusted Friendly Support
    "angry": "0b32066b-2bcc-44b9-89ab-0223a09d1606",     # Carson - Angry Friendly Support
    "surprise": "66f5935b-af2e-4ec9-bb3e-59112e9ddc93",  # Carson - Surprised Friendly Support
}

#: The default narrator. "Curious" is the only take that can carry eight unbroken minutes — the
#: other three are expressive enough to become grating over a whole script, and are meant for
#: individual beats once per-beat emotion selection exists.
NARRATOR = "curious"


def resolve_voice(voice_id: str | None = None, name: str | None = None) -> str:
    """Return the Cartesia voice id to synthesise with.

    An explicit ``voice_id`` always wins (that is where a custom clone goes). Otherwise ``name`` is
    looked up in :data:`VOICES`, falling back to :data:`NARRATOR`. An unknown ``name`` raises rather
    than silently narrating in the wrong voice — a typo that costs a paid TTS call should be loud.
    """
    if voice_id:
        return voice_id
    key = (name or NARRATOR).strip().lower()
    if key not in VOICES:
        raise ValueError(
            f"unknown CARTESIA_VOICE {key!r}; pick one of {', '.join(sorted(VOICES))} "
            f"or set CARTESIA_VOICE_ID to an explicit id"
        )
    return VOICES[key]
