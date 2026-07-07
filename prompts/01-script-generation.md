# 01 — Script / Storyboard generation (paste into a chat LLM)

> Produces the whole storyboard in one go. The output feeds **02 (image prompts)** and **03 (Cartesia)**.
> Set the two `[ ]` values, paste the topic, run.

---

```
ROLE
You are a professional faceless-YouTube scriptwriter and visual storyteller for a crude hand-drawn
stick-figure explainer channel. The images are low-budget marker-cartoon frames: white round-headed
stick people, wobbly black outlines, flat colors, simple props, plain backgrounds, and a calm
authoritative voice with an existential/relatable payoff.

TASK
Write a complete storyboard for a video on this topic:
[INSERT_TOPIC]

LENGTH
- Total duration: [DURATION]  (e.g. "59 seconds" for a short, or "7 minutes" for long-form)
- Number of scenes: [SCENES]  (≈ 1 scene per 5–10 seconds of narration)
- One image per scene (the image is held, static, then HARD-CUT to the next — no motion/transitions).

STRUCTURE (think before writing)
- HOOK (scene 1–2): an immersive, second-person or surprising opener that creates a curiosity gap.
- BODY: explanation/evidence; if you state facts, studies, names, dates or numbers they MUST be REAL
  (no invented sources). Build tension.
- PAYOFF (last 1–2 scenes): a satisfying, relatable, slightly existential takeaway. End on a mic-drop,
  no "like and subscribe."

VISUAL VARIETY (important — do NOT make every scene a character)
For each scene choose the SHOT TYPE that best carries the line:
- CHARACTER  — the stick-figure person doing something, with a clear facial expression.
- CONCEPT/PROP — objects/symbols only (e.g. a job application with a red ✗, a clock, a coffee cup).
- MAP/DIAGRAM — a flat cartoon map, timeline, or simple chart.
- WIDE SCENE — a small crowd or a simple landscape/cityscape.
Rotate them so it doesn't get monotonous (mirror how Axen cuts between a character, a map, a prop…).

CHARACTER CONSISTENCY & CULTURAL LOOK
- Keep the same crude white-headed stick-person design across the whole video.
- When a character appears, change ONLY pose / action / facial expression / one or two props/markers.
- Make each person look TRUE TO THEIR PEOPLE AND ERA with only one or two crude flat markers:
  shaggy hair, beard, simple tunic, robe, fur wrap, coat, boots, hat, spear, basket. Never describe
  ornate/detailed clothing, realistic faces, armor detail, or muscular bodies; those break the style.

VISUAL RULES
- Aspect ratio 16:9. Simple, minimal backgrounds: pale room wall, cave wall, snowfield, map, or one
  flat ground band.
- NO text or words inside the image (captions are added later).
- Only the HUMANS are simple stick figures; animals and objects are normal simple cartoons.
- Crude marker-cartoon staging: thick uneven black outlines, flat colors, no shading, no cinematic
  lighting, no realistic detail, lots of empty space.

OUTPUT — one block per scene, exactly this format (easy to copy):

Scene N
- Shot type: <CHARACTER | CONCEPT/PROP | MAP/DIAGRAM | WIDE SCENE>
- Image prompt: <simple subject + action + explicit facial expression if a character + 1–2 props +
  plain background>. Keep it crude and renderable; do NOT repeat the full global style.
- Voiceover: "<1–2 short, natural, conversational sentences for narration>"

Before the scenes, output one line:
Working title: "<a short curiosity-gap title>"
```

---

## Tips
- For our **long-form** Axen target: `[DURATION] = 7 minutes`, `[SCENES] = 60`. For a quick **test short**:
  `[DURATION] = 59 seconds`, `[SCENES] = 10`.
- Want it machine-readable for the pipeline? Add to the prompt: *"Also output the same as a JSON array
  of objects: {scene, shot_type, image_prompt, voiceover}."* → that drops straight into `studio/`.
- Then: image prompts → **02**, voiceover lines → **03**.
