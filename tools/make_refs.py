#!/usr/bin/env python3
"""Bootstrap the channel's reference images (run once; commit the chosen output to assets/refs/).

REF-1 = character model sheet (text→image). REF-2 = expression sheet (REF-1→image edit). Every
character/wide shot later passes these to Gemini so the recurring stick-figure stays on-model.
See prompts/04-gemini-reference-images.md and context/project/blueprints/gemini-image-provider.md.

Run:  python tools/make_refs.py        # writes assets/refs/character.png + expressions.png
Needs: GEMINI_API_KEY in .env + billing enabled.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

import argparse  # noqa: E402

from dotenv import load_dotenv  # noqa: E402

from tools.studio_poc import GeminiImageProvider  # noqa: E402

REFS = _ROOT / "assets/refs"

BASE_CHARACTER_PROMPT = (
    "A character model sheet for one recurring crude white-headed stick person on a plain pale "
    "background, matching a low-budget hand-drawn educational web-cartoon frame. Thick uneven black "
    "marker outlines, wobbly imperfect linework, flat fill colors only, no shading, no gradients. "
    "The character has a circular white face, tiny black dot eyes, one small black line mouth, no "
    "nose, thin black noodle arms and legs, tiny line hands and feet. {features} Show culture/clothing "
    "only as crude flat add-ons on the stick body, never as realistic anatomy or detailed costume. "
    "Front view, neutral standing pose, full body, lots of empty space, no text. Avoid: "
    "photorealistic, 3D, Pixar, Disney, anime, vector illustration, cinematic lighting, polished "
    "corporate illustration, ornate clothing, detailed face, busy background."
)

BASE_EXPRESSION_PROMPT = (
    "Using the exact crude white-headed stick person in the reference image, draw the same round "
    "white head six times in a simple grid with these marker-cartoon expressions: happy, worried, "
    "sad, surprised, angry, neutral. Keep the identical thick uneven black line weight, dot eyes, "
    "tiny line mouth, optional eyebrows, flat colors, and low-budget hand-drawn look. Plain pale "
    "background, no text."
)


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Bootstrap customizable clean stick-figure reference sheets.")
    ap.add_argument("--beard", action="store_true", help="Add a beard to the reference character")
    ap.add_argument("--hair", default=None, help="Describe hair for the character (e.g. 'messy black hair')")
    ap.add_argument("--clothes", default="simple tunic", help="Describe base clothing (e.g. 'simple tunic', 't-shirt')")
    args = ap.parse_args()

    features_list = []
    if args.beard:
        features_list.append("has a simple hand-drawn beard")
    if args.hair:
        features_list.append(f"has simple hand-drawn {args.hair}")
    if args.clothes:
        features_list.append(f"wearing a simple {args.clothes}")
    
    features_str = ", ".join(features_list)
    if features_str:
        features_str = features_str.capitalize() + "."

    char_prompt = BASE_CHARACTER_PROMPT.format(features=features_str)
    
    REFS.mkdir(parents=True, exist_ok=True)
    # Reference sheets read best square, not 16:9 → aspect_ratio=None (model default).
    provider = GeminiImageProvider(aspect_ratio=None)

    character = REFS / "character.png"
    print(f"Generating character sheet with prompt:\n  {char_prompt}\n")
    provider.generate(char_prompt, character)
    print(f"REF-1 character sheet → {character}")

    expressions = REFS / "expressions.png"
    provider.generate(BASE_EXPRESSION_PROMPT, expressions, refs=[character])
    print(f"REF-2 expression sheet → {expressions}")
    print("\nEyeball both, regenerate if off; once happy, commit assets/refs/ (the channel identity).")


if __name__ == "__main__":
    main()
