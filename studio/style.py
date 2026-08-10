"""The LOCKED visual style — the single lever that keeps every image consistent.

Target look (rebuilt from the local ``assets/refs/frame_*.jpg`` stills): a crude, low-budget
hand-drawn explainer cartoon. It is not polished illustration. Frames have thick uneven black
marker outlines and flat fill colors. Humans are white round-headed stick people with dot eyes and
one small line mouth; hair, beards, coats, tunics, or fur wraps are simple flat shapes attached to
that stick body. Animals, houses, maps, bones, fires, snow, furniture, and tools are normal simple
cartoons, not stick figures.

**Rewritten 2026-08-09.** The previous version mandated "plain pale background", "mid-distance
view" and "lots of empty space", and banned all on-screen marks. Measured against the reference
frames, all four were wrong: backgrounds there are rich and location-specific, scale ranges from a
lone tiny figure to a face filling the frame, and arrows, leader lines and colour-coded overlays
are one of its signature devices. Those clauses produced 0.879 mean pairwise layout similarity
across a 60-image run with 57% of frames in one horizontal band. Evidence and method:
``context/research/2026-08-09/01-render-quality-gap.md``.

Consistency across ~60 images/video is the hard part. No image provider (Agnes = OpenAI-compatible;
Gemini "Nano Banana") exposes a negative-prompt field, so the whole look — positives AND negative
list — rides in the prompt TEXT. A reference image (REF-1/REF-2 in assets/refs/) stacks on top when
a provider uses one. Keep `LOCKED_STYLE` tight and concrete; per-scene prompts carry the subject and
facial expression, while this module owns the art direction.
"""

from __future__ import annotations

#: Appended to every character/wide image prompt so all frames share one look. Tight on purpose —
#: the refs are crude web-cartoon stills, not refined vector art. KEY: solid wobbly black outlines,
#: white round heads, noodle stick limbs, flat colors, and the REAL location as flat colour blocks.
#: Framing is deliberately NOT specified here — it varies per shot via :data:`FRAMINGS`.
LOCKED_STYLE = (
    "Crude hand-drawn educational web-cartoon frame, like a simple marker drawing. Thick uneven "
    "black outlines, wobbly imperfect linework, flat fill colors only, no shading, no gradients, "
    "no painterly texture. Draw ONLY the one place named in the subject above, as flat blocks of "
    "colour filling the frame — do not add any other location, and do not leave the background as "
    "empty white paper. Any human drawn is a simple white round-headed stick person: round "
    "white "
    "face, tiny black dot eyes, one small black line mouth, optional tiny eyebrows, no nose, no "
    "detailed face; thin black noodle arms and legs, tiny line hands and feet. Show culture and "
    "era only with one or two crude flat add-ons: shaggy hair, beard, simple "
    "tunic, blue shirt, robe, fur wrap, coat, boots, hat, or spear. Never draw a realistic body or "
    "detailed costume. ONLY humans are stick figures; animals, objects, maps, bones, fires, "
    "houses, furniture, snow, and landscapes are normal simple hand-drawn cartoons, not stick "
    "figures. Keep it amateur, rough, funny-looking but readable"
)

#: Figure-count cap. Deliberately a SEPARATE clause placed near the front of the prompt rather than
#: buried at the end of ``LOCKED_STYLE`` — in the 2026-08-09 probe the trailing version was ignored
#: and frames still came back with six to eight figures in a row.
FIGURE_CAP = (
    "CRITICAL: draw exactly the people the subject above names and no one else. Do not add "
    "bystanders, onlookers, a group, a crowd, or a line of figures in the background"
)

#: The reference's diagram notation — orange for heat, blue for cold or water, a flat yellow or red
#: fill on the thing under discussion, arrows pointing at it, a red question mark for an unknown.
#: Present in roughly a third of sampled reference frames
#: (``context/research/2026-08-09/01-render-quality-gap.md`` §4b).
#:
#: **This is NOT appended to image prompts.** It was, briefly, on 2026-08-09, and the probe came
#: back with every mark in the list stamped onto every frame: a red question mark, a red cross,
#: orange squiggles and blue arrows, all six of six images. A model reads an enumeration in a
#: prompt as a checklist, not a menu. So the vocabulary lives here as the writer's reference — it
#: is quoted into ``studio.script_prompt``, which asks the script LLM to name AT MOST ONE mark per
#: beat inside that beat's ``image_prompt``. By the time a prompt reaches the image model, the one
#: mark that scene wants is part of the subject, and ``LOCKED_STYLE`` says to draw no others.
OVERLAY_LANGUAGE = (
    "thin black leader lines and curved arrows pointing at the thing being described; orange "
    "squiggles and arrows for heat; blue arrows and lines for cold, wind or water; a flat yellow "
    "or red fill highlighting the single part under discussion; a large red question mark for an "
    "unknown; a large red cross for something that does not work"
)

#: Framing directives. The measured failure of the previous style was that NOTHING varied the
#: camera: 57% of one run's frames put their subject mass in the same horizontal band and mean
#: pairwise layout similarity was 0.879. Framing is now chosen per shot by
#: ``studio.framing.plan_framings`` and injected here, so variety is structural rather than a thing
#: the prompt politely requests.
#:
#: These names are deliberately DISJOINT from ``studio.types.SHOT_TYPES``. When framing offered
#: a "wide" and shot_type also offered a "wide", the script LLM began writing framing values
#: into shot_type and a real run died on ``shot_type: "detail"``. Two overlapping vocabularies
#: in one JSON object is an invitation to cross them.
FRAMINGS: dict[str, str] = {
    "close_up": (
        "EXTREME CLOSE-UP: one head, one pair of hands, or one object fills most of the frame and "
        "is cropped by the frame edge. No full bodies"
    ),
    "medium": (
        "MEDIUM SHOT: one or two figures seen from roughly the waist up, close enough to read the "
        "expression, cropped by the bottom edge"
    ),
    "establishing": (
        "WIDE ESTABLISHING SHOT: small figures placed low in the frame, the environment filling "
        "most of the height"
    ),
    "detail": (
        "SINGLE OBJECT: one prop alone in the frame, drawn large and centred, no people at all"
    ),
    "cutaway": (
        "CROSS-SECTION CUTAWAY: the ground, a shelter, a cave or a hut sliced open from the side "
        "so the inside and its layers are visible"
    ),
    "over_shoulder": (
        "OVER THE SHOULDER: seen from behind and just past one figure, looking at what they are "
        "looking at. That figure is large, close, and cropped"
    ),
    "profile": (
        "SIDE PROFILE: figures seen from the side, facing each other or facing across the frame, "
        "staged at clearly different distances from the viewer"
    ),
}

#: Concept/map shots (props, symbols, diagrams, geography) must NOT contain a person — and must NOT
#: sprout faces on objects/continents. They still match the same ``assets/refs`` visual grammar:
#: crude marker lines, flat colors, plain backgrounds, simple arrows/symbols, no realistic
#: rendering.
CONCEPT_STYLE = (
    "crude hand-drawn educational web-cartoon diagram of objects, props, maps, symbols, or scenery "
    "ONLY; thick uneven black marker outlines, wobbly imperfect linework, flat fill colors only, "
    "large readable shapes, amateur marker-drawing look. Set the object in its real place — on "
    "earth, snow, cave floor, water, a worked surface — as flat blocks of colour rather than "
    "floating on empty white"
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
#: No GLYPHS from the model — but marks are wanted.
#:
#: This used to be a blanket "no text, no signs, no labels, no symbols" on every prompt path. That
#: was over-drawn. The reference labels things constantly (leader lines onto a seal, a labelled
#: diagram, a clock face) and arrows are one of its signature devices; banning all of it threw out
#: the device along with the problem. The real constraint is narrower: image models garble
#: *letterforms*, not shapes. So glyphs are refused and drawn deterministically in post by the PIL
#: callout layer (``studio.narration.emphasis_timeline`` -> ``tools.studio_poc``), while arrows,
#: leader lines, highlight fills and symbols are asked for explicitly.
NO_WORDS = (
    "No letters, words, digits, dates, signs, captions, writing or watermark anywhere in the image "
    "— the model garbles letterforms and every real label is drawn afterwards in post. Wordless "
    "MARKS are wanted and welcome: arrows, leader lines, highlight fills, question marks, crosses "
    "and simple symbols"
)

#: Back-compat alias. Kept because the thumbnail path and older callers still import ``NO_TEXT``;
#: they get the same narrowed rule.
NO_TEXT = NO_WORDS
FRAME = "16:9 wide composition"

#: The user's exact NEGATIVE-prompt list. No image provider (Agnes/Gemini) exposes a negative-prompt
#: field, so we append it as text (``Avoid: …``) on every prompt path — the only portable way to
#: push the model off photoreal/3D/vector/cinematic looks and hold the hand-drawn explainer style.
NEGATIVE_PROMPT = (
    "photorealistic, 3D, Pixar, Disney, anime, manga, hyper detailed, oil painting, watercolor, "
    "cinematic lighting, ultra realistic, AI art, concept art, digital painting, vector "
    "illustration, clean corporate illustration, polished mascot art, professional infographic, "
    "gradient mesh, HDR, sharp rendering, highly textured, ornate, realistic human anatomy, "
    "detailed faces, detailed clothing, a row of figures lined up facing the viewer, "
    "empty white background"
)
# "busy background" and "complex composition" were removed on 2026-08-09: they were suppressing the
# location-specific environments the reference actually uses. The two clauses added in their place
# push against the two failures that were measured instead (the lineup, and the white void).


def _avoid() -> str:
    """The trailing ``Avoid: …`` clause carrying :data:`NEGATIVE_PROMPT` (on every prompt path)."""
    return f"Avoid: {NEGATIVE_PROMPT}."


#: Thumbnail styling: COMPLETELY the same hand-drawn stickman look as the video (LOCKED_STYLE +
#: NO_REALISTIC_HUMANS + the Avoid: negatives, so no photoreal / 3D / cinematic background sneaks
#: in) — only the COMPOSITION changes: one big centred focal stick figure, an exaggerated intense
#: expression, bold high-contrast readable layout. This layer carries composition ONLY (no
#: cinematic/vibrant/polished words — those pulled the earlier render into a realistic scene). Title
#: text is added in post (PIL).
THUMBNAIL_STYLE = (
    "Composed as a bold YouTube history thumbnail while keeping the same crude marker-cartoon "
    "look: ONE large white-headed stick-person or one large simple prop, big surprised or intense "
    "dot-eye expression, one or two oversized clear props, plain flat background, strong readable "
    "silhouette, left-side focal subject with empty space for title text"
)


def thumbnail_prompt(subject: str) -> str:
    """Prompt for a text-free thumbnail image (the title is overlaid later with PIL).

    COMPLETELY the stickman look: the full video :data:`LOCKED_STYLE` + :data:`NO_REALISTIC_HUMANS`
    + the ``Avoid:`` negatives (so no photoreal / 3D / cinematic background) — with
    :data:`THUMBNAIL_STYLE` adding only the punchy thumbnail COMPOSITION on top. Only ``NO_TEXT``
    also rides along (the title is added in post via PIL)."""
    subject = subject.strip().rstrip(".")
    return (
        f"{subject}. {LOCKED_STYLE}. {THUMBNAIL_STYLE}. {NO_REALISTIC_HUMANS}. "
        f"{FRAME}, {NO_TEXT}. {_avoid()}"
    )

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
    framing: str = "",
) -> str:
    """Combine a scene's subject with the right per-model guardrail set for its shot.

    Three explicit templates, so each model gets exactly what it needs:

    * **Gemini character/wide with refs** (``use_character_ref``) — wrap in an explicit "use the
      SAME character from the reference image" instruction so the figure stays on-model.
    * **concept / map** (no character) — the people-free ``CONCEPT_STYLE`` + ``NO_PEOPLE`` so FLUX
      doesn't draw a stick-figure onto a map or a prop shot.
    * **character/wide without refs** — the locked character ``style`` + ``NO_WORDS``.

    ``framing`` is a key of :data:`FRAMINGS` (see ``studio.framing.plan_framings``, which assigns
    one per shot). It is placed immediately after the subject and before the style block, because
    the style block is ~250 words and anything appended after it competes with all of them. An
    unknown or empty ``framing`` simply omits the directive rather than guessing.
    """
    subject = image_prompt.strip().rstrip(".")
    shot = f" {FRAMINGS[framing]}." if framing in FRAMINGS else ""
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
            f"{CHARACTER_REF_PREAMBLE}{subject}.{shot} {FIGURE_CAP}.{CHARACTER_REF_SUFFIX} "
            f"{style}. {character_count} {NO_REALISTIC_HUMANS}. {FRAME}, {NO_WORDS}. "
            f"{_avoid()}"
        )
    if shot_type in ("concept", "map"):
        return (
            f"An empty scene showing only objects and scenery — absolutely NO people, NO stick "
            f"figures, NO figures of any kind. {subject}.{shot} {CONCEPT_STYLE}. "
            f"{NO_PEOPLE}, {NO_WORDS}. {FRAME}. {_avoid()}"
        )
    # character/wide without refs: locked stick-figure style + the explicit no-realistic / no-photo
    # negative (leading with a long preamble instead pushed ornate subjects to photorealism).
    return (
        f"{subject}.{shot} {FIGURE_CAP}. {style}. {NO_REALISTIC_HUMANS}. "
        f"{FRAME}, {NO_WORDS}. {_avoid()}"
    )
