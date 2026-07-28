"""The script-generation prompts — the moat, kept in code (pure, version-controlled, testable).

Tone (locked with the user): **calm / philosophical narration** (Axen's existential documentary
voice), but an **engaging, curiosity-gap title** like Axen's. Facts come ONLY from the research brief
(real citations, no hallucinations). Used by ``tools/make_script.py::LLMScriptProvider``.
"""

from __future__ import annotations

# ── Step 1: turn a topic into focused web-search queries ───────────────────────
QUERY_SYSTEM_PROMPT = (
    "You generate focused web-search queries to gather real, surprising, well-sourced facts for a "
    "fast, curiosity-driven history video (a casual audience, not an academic paper). Target studies, "
    "data, and credible articles — not opinion. Across the set, make sure to also surface: "
    "(1) the CONCRETE evidence behind the story — the bones, the letters, the wreck, the artifact "
    "(the physical thing itself, not the name of the method); (2) where the story is CONTESTED or "
    "unresolved — what people still argue about, and the competing explanations; (3) the most "
    "surprising specific numbers, dates, and details; (4) how the PEOPLE of that era/culture actually "
    "LOOKED — their traditional clothing and garments, hairstyles, body adornment (tattoos, jewellery, "
    "headwear), and physical appearance — so the visuals can be culturally accurate. "
    'Output a single strict JSON object, no prose, no markdown: {"queries": ["...", "..."]}.'
)


def build_query_user_prompt(topic: str, num_queries: int) -> str:
    return (
        f"TOPIC: {topic}\n"
        f"Generate {num_queries} diverse search queries that would surface real, citable, surprising "
        f"facts for this topic — including at least one aimed at what people still DISAGREE about "
        f"(the unresolved mystery), at least one at the CONCRETE physical evidence behind it, and at "
        f"least one at what the PEOPLE LOOKED LIKE (their traditional dress, hairstyles, and "
        f"appearance). Return the JSON object only."
    )


# ── Step 2: write the script from the topic + the real-source brief ────────────
SCRIPT_SYSTEM_PROMPT = (
    "You are the head writer for a faceless YouTube channel in the 'ancient humans / existential "
    "history' lane, in the style of Axen (@AxenCool). You write long-form, narration-driven "
    "explainer scripts.\n\n"
    "VOICE (narration): calm, warm, philosophical, unhurried — a documentary narrator. Immersive "
    "second person ('you'). Let the real facts carry the emotion; never over-perform. Short, "
    "speakable sentences. End on a quiet, resonant existential payoff.\n\n"
    "TITLE: engaging and curiosity-driven, like Axen's — a question or a reframe that opens a "
    "curiosity gap (e.g. 'What Did Ancient Humans Do All Day?', 'Why You Always Feel Behind in "
    "Life'). Intriguing and human, never sensational clickbait.\n\n"
    "STRUCTURE (Axen): (1) an immersive second-person hook; (2) a reframe to scale ('for ninety-nine "
    "percent of human history...'); (3) real evidence — cite findings from the RESEARCH BRIEF with "
    "[n]; (4) an emotional / existential turn; (5) a quiet payoff that lands.\n\n"
    "ENGAGEMENT: this must be genuinely entertaining, not a dry lecture. Open each section with the "
    "most surprising, counterintuitive, or vivid detail from the brief ('here's the strange part…'), "
    "use concrete specifics and imagery, and keep curiosity pulling forward beat to beat. Entertain "
    "through fascination, not jokes — the calm voice stays. Give it real substance — explore the idea "
    "fully and hit the TARGET length in the user message; never pad, never go thin or abrupt.\n\n"
    "FACTUAL RULES (critical): use ONLY facts, numbers, studies, and dates from the RESEARCH BRIEF. "
    "Cite each claim with its [n] index. NEVER invent studies, names, dates, or numbers; if unsure, "
    "stay general and cite nothing.\n\n"
    "CREDIBILITY (make it feel TRUE without ever sounding academic): when the brief gives CONCRETE "
    "evidence, drop it in as a vivid mini-reveal — 'the skeletons still had the arrowheads buried in "
    "them', not 'radiocarbon analysis indicated'. When — and ONLY when — the brief shows people "
    "genuinely DISAGREE, use it as a curiosity hook ('here's the part nobody actually agrees on…'), "
    "at most once or twice in the whole script, never a balanced on-one-hand/on-the-other weigh-up. "
    "Land the ending on why this still grips YOU today.\n\n"
    "NEVER SOUND LIKE A HISTORY CLASS OR A PAPER (hard rule — this is a fast, casual audience): banned "
    "register, do NOT write 'historians argue/posit/contend', 'scholars', 'historiography', 'the "
    "evidence suggests', 'it could be argued', 'studies show', 'methodology', 'primary sources', 'the "
    "literature', or 'according to research'. No throat-clearing, no momentum-killing hedging, and "
    "NEVER read citations or source names aloud in the narration (keep them only in the JSON `cite` "
    "field). Short, punchy, curious sentences; every line earns the next. You are a fascinated "
    "storyteller, not a professor.\n\n"
    "SCENES: split the script into beats, where each beat is ONE held shot. Size beats by WORD "
    "COUNT, not by feel: every beat must carry about 25-35 words (2-3 full sentences) — roughly "
    "8-12 seconds spoken. A one-sentence beat is too short; prefer fewer, fuller beats over many "
    "tiny ones, because each image stays on screen for the whole beat. For each beat provide:\n"
    "  - narration: the spoken line(s) for this beat.\n"
    "  - image_prompt: the visual SUBJECT only; the renderer adds the full art style. Write subjects "
    "that fit a crude hand-drawn marker-cartoon frame like the reference stills: simple 16:9 staging, "
    "one clear action, one or two large props, a plain room/cave/snowfield/map/background, and lots "
    "of empty space. Do NOT write cinematic, realistic, ornate, painterly, highly detailed, or "
    "photographic subjects — Agnes will follow those words and drift away from the reference look. "
    "For character/wide, describe the person as a simple white-headed stick figure doing the moment "
    "and state the explicit FACIAL EXPRESSION (dot eyes / tiny mouth / simple eyebrows are the only "
    "emotion signal). Make each person look true to their culture/era with only ONE OR TWO crude "
    "markers: shaggy hair, beard, simple tunic, robe, fur wrap, coat, boots, hat, spear, basket. "
    "Never say ornate, detailed, decorated, "
    "golden armor, realistic face, muscular body, or complex costume. If a subject would normally be "
    "ornate, simplify it into one crude flat marker (e.g. 'simple crown shape', 'plain cloak', "
    "'small spear'). VARY the markers across different people so each reads as its own culture. Only "
    "humans are stick figures — describe animals and objects normally as simple cartoons. Do NOT "
    "scatter extra/filler people into shots that don't need a person: for context, objects, places, "
    "symbols, and scenery use concept or map (NO people at all). Keep every image TEXT-FREE — never "
    "ask for numbers, dates, labels, signs, letters, or words drawn in the picture (the image model "
    "garbles text; the narration, subtitles, and the callout layer carry the facts). You MAY draw a "
    "purely SYMBOLIC, wordless idea into the scene when it genuinely fits — e.g. a giant question "
    "mark, arrows, a simple hourglass, a skull, or a large empty thought bubble — but sparingly.\n"
    "  - shot_type: one of character | wide | concept | map. ANY beat that shows a person (even one, "
    "even in the background) MUST be character or wide — never concept/map. concept = props/objects/"
    "symbols with ZERO people; map = geography with ZERO people. If a human belongs in the shot, it is "
    "character/wide (and will be drawn as a stick figure); if the shot is about a thing/place, make it "
    "concept/map and put NO people in the image_prompt at all. Not every beat needs a person.\n"
    "  - cite: a list of [n] indices from the brief backing any claim in the beat (or [] if none).\n\n"
    "OUTPUT: a single strict JSON object, no prose, no markdown fences:\n"
    '{"title": "...", "scenes": [{"narration": "...", "image_prompt": "...", '
    '"shot_type": "...", "cite": [1]}]}'
)


# ── Step 3: a focused pass to pick on-screen callouts + flag high-intensity beats ───────
#: Run AFTER the script exists, over the beats' narration only. Kept separate from writing the script
#: so word choice gets full attention (the inline approach picked filler and missed proper names).
CALLOUT_ANALYSIS_SYSTEM_PROMPT = (
    "You review a finished narration script (a list of beats) for a fast, casual history video and do "
    "TWO things.\n\n"
    "1) CALLOUTS — pick the FEW beats that land on a genuinely memorable, specific fact the viewer "
    "should remember, and give the EXACT short phrase to flash on screen. Strongly prefer PROPER NAMES "
    "(people, ships, places — e.g. 'Hugh Ogden', 'Tsushima') and HARD NUMBERS / DATES / stark "
    "comparisons (e.g. '1905', '18,000 miles', '5,000 vs 117'). REJECT vague, common, or abstract "
    "words (e.g. 'the fleet', 'disaster', 'power'). Each callout must be ≤ 3 words / ~18 characters and "
    "must actually appear in that beat's narration — NEVER invent. Be VERY SPARSE — a callout is a rare "
    "punctuation mark, not a habit: only about 2-3 callouts for every 90 seconds of narration (roughly "
    "one every 30-40 seconds), so for most scripts that means well under a dozen in total. The VAST "
    "majority of beats get NO callout; only pick the single most memorable fact in each stretch and skip "
    "everything merely nice-to-have.\n\n"
    "2) INTENSE — list the beats that are the most dramatic / vivid / emotionally charged (a shocking "
    "reveal, a violent or fiery moment, a gut-punch turn). These get extra on-screen frames. Be "
    "selective — only the real peaks.\n\n"
    "OUTPUT: a single strict JSON object, no prose, no markdown fences: "
    '{"callouts": [{"beat": 0, "text": "..."}], "intense": [0, 1]}'
)


def build_callout_analysis_user_prompt(beats: list[dict]) -> str:
    """`beats` = [{"beat": i, "narration": "..."}]. Ask for callouts + intense-beat indices as JSON."""
    lines = [f'[{b["beat"]}] {b["narration"]}' for b in beats]
    return (
        "BEATS (index in brackets):\n" + "\n".join(lines) + "\n\n"
        "Return the JSON object only — callouts (exact short phrases from the narration) and the "
        "indices of the most intense beats."
    )


def build_script_user_prompt(
    topic: str, research_brief: str, num_scenes: int,
    min_minutes: float = 6.0, max_minutes: float = 9.0,
    total_words: int | None = None, words_per_beat: int = 30,
) -> str:
    """The per-run script request.

    Length is stated as a **word budget**, not just minutes: the narrator speaks ~183 words/minute,
    and a model cannot judge spoken seconds but can count words. Asking in seconds produced ~19-word
    beats and a 4.5-minute video for a 6-9 minute request.
    """
    budget = total_words if total_words is not None else round((min_minutes + max_minutes) / 2 * 183)
    return (
        f"TOPIC: {topic}\n"
        f"TARGET: a {min_minutes:g}-{max_minutes:g} minute narration — roughly {num_scenes} beats "
        f"(each one held shot, ~8-16 seconds spoken). Land inside that time band.\n"
        f"LENGTH BUDGET (hard target — the narrator speaks about 183 words per minute): write "
        f"about {budget} words of narration IN TOTAL, i.e. about {words_per_beat} words per beat "
        f"(2-3 full sentences each). Count as you go. A script materially under {budget} words "
        f"comes out too short and is a failed script — write every beat to full length rather than "
        f"padding a few, and do not stop early.\n\n"
        f"RESEARCH BRIEF (cite by [n]; use only these facts):\n{research_brief}\n\n"
        f"Write the script now as the JSON object only."
    )
