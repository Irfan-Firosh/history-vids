# 02 — Image prompts (paste into the image generator)

> Each scene's final image prompt = **scene contents (from 01)** + **CHARACTER BASE** (only if a
> character is in the shot) + **STYLE BASE**. The style is rebuilt from the local `assets/refs/frame_*.jpg`
> reference stills: crude hand-drawn explainer frames, not polished illustration.

## STYLE BASE — append to EVERY image (character or not)
```
crude hand-drawn educational web-cartoon frame, like a simple marker drawing from the local assets/refs video stills. Thick uneven black outlines, wobbly imperfect linework, flat fill colors only, no shading, no gradients, no painterly texture. Plain pale background (white, light grey, pale blue, or pale yellow) with one simple flat ground band when needed. Clear wide 16:9 staging, mid-distance view, large simple props, lots of empty space, diagram-like composition. EVERY human is a simple white round-headed stick person: circular white face, tiny black dot eyes, one small black line mouth, optional tiny eyebrows, no nose, no detailed face; thin black noodle arms and legs, tiny line hands and feet. Show culture and era only with one or two crude flat add-ons on the stick person: shaggy hair, beard, simple tunic, blue shirt, robe, fur wrap, coat, boots, hat, or spear. Never draw a realistic body or detailed costume. ONLY humans are stick figures; animals, objects, maps, bones, fires, houses, furniture, snow, and landscapes are normal simple hand-drawn cartoons, not stick figures. Use a small flat color palette with simple accent colors; keep the frame uncluttered, amateur, rough, funny-looking but still readable, no text
```
(Matches `studio/style.py::LOCKED_STYLE`. Agnes gets this as prompt text; Gemini/Cloudflare can also
receive REF-1/REF-2 when those committed files exist.)

## NEGATIVE — append to EVERY image (as `Avoid: …`; no provider has a negative-prompt field)
```
Avoid: photorealistic, 3D, Pixar, Disney, anime, manga, hyper detailed, oil painting, watercolor, cinematic lighting, ultra realistic, AI art, concept art, digital painting, vector illustration, clean corporate illustration, polished mascot art, professional infographic, gradient mesh, HDR, sharp rendering, highly textured, ornate, busy background, complex composition, realistic human anatomy, detailed faces, detailed clothing
```
(Matches `studio/style.py::NEGATIVE_PROMPT`.)

## CHARACTER BASE — append ONLY when the scene has the stick-figure person
```
crude white-headed stick person: circular white face, tiny black dot eyes, one small black line mouth, optional tiny eyebrows, no nose, thin black noodle arms and legs, tiny line hands and feet. Add only one or two crude flat markers for era/culture: shaggy hair, beard, simple tunic, robe, fur wrap, coat, boots, hat, spear, basket.
```
Then change ONLY: pose · action · **facial expression** · one or two crude clothing/hair/prop markers.

## Shot types — what to send per scene
| Shot type | Send | Character base? |
|---|---|---|
| **CHARACTER** | one stick person + explicit expression + 1–2 props + plain bg + CHARACTER BASE + STYLE BASE | ✅ yes |
| **CONCEPT/PROP** | objects/symbols/scenery only, no people/faces/text + CONCEPT STYLE | ❌ no |
| **MAP/DIAGRAM** | simple map/timeline/arrows/geography only, no people/faces/text + CONCEPT STYLE | ❌ no |
| **WIDE SCENE** | small group of crude white-headed stick people + simple landscape/interior + STYLE BASE | ✅ yes |

## Worked examples
**Character (calm):**
```
a crude white-headed stick person sitting cross-legged beside a simple campfire, relaxed dot eyes,
small calm smile, plain pale cave wall behind — [CHARACTER BASE] — [STYLE BASE]
```
**Character (stressed) — your reference scene:**
```
a crude white-headed stick person in a simple blue shirt walking past a door, worried eyebrows,
tiny downturned mouth, holding a briefcase and coffee cup, one flat brown floor band — [CHARACTER BASE] — [STYLE BASE]
```
**Concept/prop (no character):**
```
a job application paper, a coffee cup, and a big red X shape, simple black arrows, plain white
background, no words or labels — [CONCEPT STYLE]
```
**Map (no character):**
```
a simple flat cartoon world map with green land shapes, blue water, one black route arrow,
plain white border, no labels or words — [CONCEPT STYLE]
```

## Consistency knobs
- **Agnes consistency** comes mostly from the exact same style text every call; do not let scene prompts
  say realistic/cinematic/ornate.
- **Gemini/Cloudflare consistency** can add REF-1/REF-2 reference conditioning when
  `assets/refs/character.png` and `assets/refs/expressions.png` exist.
- The **face is the only emotion signal** — always state the expression explicitly.
