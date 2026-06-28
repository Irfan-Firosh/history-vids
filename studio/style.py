"""The LOCKED visual style — the single lever that keeps every image consistent.

Target look (rebuilt from the local ``assets/refs/frame_*.jpg`` stills): a crude, low-budget
hand-drawn explainer cartoon. It is not polished illustration. Frames have thick uneven black
marker outlines, flat fill colors, plain pale backgrounds, simple props, and diagram-like staging.
Humans are white round-headed stick people with dot eyes and one small line mouth; hair, beards,
coats, tunics, or fur wraps are simple flat shapes attached to that stick body. Animals, houses,
maps, bones, fires, snow, furniture, and tools are normal simple cartoons, not stick figures.

Consistency across ~60 images/video is the hard part. No image provider (Agnes = OpenAI-compatible;
Gemini "Nano Banana") exposes a negative-prompt field, so the whole look — positives AND negative
list — rides in the prompt TEXT. A reference image (REF-1/REF-2 in assets/refs/) stacks on top when
a provider uses one. Keep `LOCKED_STYLE` tight and concrete; per-scene prompts carry the subject and
facial expression, while this module owns the art direction.
"""

from __future__ import annotations

#: Appended to every character/wide image prompt so all frames share one look. Tight on purpose —
#: the refs are crude web-cartoon stills, not refined vector art. KEY: solid wobbly black outlines,
#: white round heads, noodle stick limbs, flat colors, simple staging, lots of empty background.
LOCKED_STYLE = (
    "Crude hand-drawn educational web-cartoon frame, like a simple marker drawing from the local "
    "assets/refs video stills. Thick uneven black outlines, wobbly imperfect linework, flat fill "
    "colors only, no shading, no gradients, no painterly texture. Plain pale background (white, "
    "light grey, pale blue, or pale yellow) with one simple flat ground band when needed. Clear "
    "wide 16:9 staging, mid-distance view, large simple props, lots of empty space, diagram-like "
    "composition. EVERY human is a simple white round-headed stick person: circular white face, "
    "tiny black dot eyes, one small black line mouth, optional tiny eyebrows, no nose, no detailed "
    "face; thin black noodle arms and legs, tiny line hands and feet. Show culture and era only "
    "with one or two crude flat add-ons on the stick person: shaggy hair, beard, simple tunic, "
    "blue shirt, robe, fur wrap, coat, boots, hat, or spear. Never draw a realistic body or "
    "detailed costume. ONLY humans are stick figures; animals, objects, maps, bones, fires, "
    "houses, furniture, snow, and landscapes are normal simple hand-drawn cartoons, not stick "
    "figures. Use a small flat color palette with simple accent colors; keep the frame "
    "uncluttered, amateur, rough, funny-looking but still readable, no text"
)

#: Concept/map shots (props, symbols, diagrams, geography) must NOT contain a person — and must NOT
#: sprout faces on objects/continents. They still match the same ``assets/refs`` visual grammar:
#: crude marker lines, flat colors, plain backgrounds, simple arrows/symbols, no realistic
#: rendering.
CONCEPT_STYLE = (
    "crude hand-drawn educational web-cartoon diagram of objects, props, maps, symbols, or scenery "
    "ONLY; thick uneven black marker outlines, wobbly imperfect linework, flat fill colors only, "
    "plain pale background, simple ground band if needed, large readable shapes, lots of empty "
    "space, amateur marker-drawing look matching the local assets/refs stills"
)
#: Concept/map negative — objects & scenery ONLY. Hardened: people-implying subjects (a "market",
#: a "battle") and the odd LLM mislabel were still sprouting stick figures into concept shots.
NO_PEOPLE = (
    "absolutely no people, no persons, no stick figures, no characters, no crowds, no human or "
    "animal figures, nothing with a face — objects and scenery ONLY"
)
#: Character/wide negative — every human MUST be a plain stick figure, never realistic. The positive
#: LOCKED_STYLE alone still let some detailed people slip through; models honour an explicit
#: exclusion, so state it. Appended on every character/wide path (with refs and without).
NO_REALISTIC_HUMANS = (
    "EVERY human must remain a crude white round-headed stick person with thin black line limbs, "
    "drawn in flat 2D marker-cartoon style — NOT a photo, NOT photorealistic, NOT 3D; no realistic "
    "or detailed people, no lifelike faces, no noses, no muscular bodies, no fully-drawn anatomy, "
    "no ornate costume detail"
)
#: Strict no-model-text guardrail — ALL on-screen text is added later with PIL (subtitles +
#: callouts), never drawn by the model (which garbles it). Maximal + on every image-prompt path.
NO_TEXT = (
    "absolutely no text, no words, no letters, no numbers, no signs, no labels, no captions, "
    "no writing, no watermark anywhere in the image"
)
FRAME = "16:9 wide composition"

#: The user's exact NEGATIVE-prompt list. No image provider (Agnes/Gemini) exposes a negative-prompt
#: field, so we append it as text (``Avoid: …``) on every prompt path — the only portable way to
#: push the model off photoreal/3D/vector/cinematic looks and hold the hand-drawn explainer style.
NEGATIVE_PROMPT = (
    "photorealistic, 3D, Pixar, Disney, anime, manga, hyper detailed, oil painting, watercolor, "
    "cinematic lighting, ultra realistic, AI art, concept art, digital painting, vector "
    "illustration, clean corporate illustration, polished mascot art, professional infographic, "
    "gradient mesh, HDR, sharp rendering, highly textured, ornate, busy background, complex "
    "composition, realistic human anatomy, detailed faces, detailed clothing"
)


def _avoid() -> str:
    """The trailing ``Avoid: …`` clause carrying :data:`NEGATIVE_PROMPT` (on every prompt path)."""
    return f"Avoid: {NEGATIVE_PROMPT}."

#: Kept for any seed-based provider. Gemini uses reference conditioning (assets/refs/), not seeds.
STYLE_SEED = 770077

#: Flat cartoon palette (used by the PoC placeholder renderer; mirrors the target look).
PALETTE = {
    "bg_top": (244, 240, 232),   # off-white paper
    "bg_bottom": (228, 222, 210),
    "accent": (40, 40, 40),      # black ink
    "text": (28, 28, 28),
    "muted": (120, 120, 120),
}


#: Prepended on character/wide shots to keep people consistent frame-to-frame WITHOUT forcing a
#: named/distinctive protagonist (no signature accessory) — the look comes from ``LOCKED_STYLE``; a
#: reference image, when a provider actually uses one, stacks on top.
CHARACTER_REF_PREAMBLE = (
    "Using the crude white-headed stick-person identity and marker-line style of the reference "
    "image, illustrate this moment: "
)
CHARACTER_REF_SUFFIX = (
    " Keep the round white head, dot eyes, tiny line mouth, thin black noodle limbs, crude flat "
    "clothing shapes, line weight, proportions, and low-budget hand-drawn look consistent with the "
    "reference image."
)


def styled_prompt(
    image_prompt: str,
    style: str = LOCKED_STYLE,
    use_character_ref: bool = False,
    shot_type: str = "character",
) -> str:
    """Combine a scene's subject with the right per-model guardrail set for its shot.

    Three explicit templates, so each model gets exactly what it needs:

    * **Gemini character/wide with refs** (``use_character_ref``) — wrap in an explicit "use the
      SAME character from the reference image" instruction so the figure stays on-model.
    * **concept / map** (no character) — the people-free ``CONCEPT_STYLE`` + ``NO_PEOPLE`` so FLUX
      doesn't draw a stick-figure onto a map or a prop shot.
    * **character/wide without refs** — the locked character ``style`` + ``NO_TEXT`` (all on-screen
      text is added later with PIL, never drawn by the model).
    """
    subject = image_prompt.strip().rstrip(".")
    if use_character_ref:
        character_count = (
            "Exactly one white-headed stick person."
            if shot_type == "character"
            else (
                "A small simple group of white-headed stick people is allowed when the scene "
                "needs it."
            )
        )
        return (
            f"{CHARACTER_REF_PREAMBLE}{subject}.{CHARACTER_REF_SUFFIX} {style}. "
            f"{character_count} {NO_REALISTIC_HUMANS}. {FRAME}, {NO_TEXT}. {_avoid()}"
        )
    if shot_type in ("concept", "map"):
        return (
            f"An empty scene showing only objects and scenery — absolutely NO people, NO stick "
            f"figures, NO figures of any kind. {subject}. {CONCEPT_STYLE}. {NO_PEOPLE}, {NO_TEXT}. "
            f"{FRAME}. {_avoid()}"
        )
    # character/wide without refs: locked stick-figure style + the explicit no-realistic / no-photo
    # negative (leading with a long preamble instead pushed ornate subjects to photorealism).
    return f"{subject}. {style}. {NO_REALISTIC_HUMANS}. {FRAME}, {NO_TEXT}. {_avoid()}"
