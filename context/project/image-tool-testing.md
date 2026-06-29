# Image-Tool Testing Guide — picking the generator for the stick-figure cartoon style

> ## ✅ DECISION (resolved): winner = **Gemini 2.5 Flash Image ("Nano Banana")**
> Validated live — nailed the style first try and stays **character-consistent across scenes** via
> reference conditioning (REF-1/REF-2), so no LoRA needed. Wired as `GeminiImageProvider`
> (`tools/studio_poc.py` + pure `studio/gemini.py`). **Note: the API has NO free image quota — needs
> billing enabled** (the ~500/day free tier is the AI-Studio *web UI* only); ~$0.039/img flat.
> fal/FLUX dropped (no free API credits). See `blueprints/gemini-image-provider.md` +
> `prompts/04-gemini-reference-images.md`. The notes below are archived for reference.

> Goal: try the **same prompt** in each tool, see which gives the best **flat stick-figure cartoon**
> with **expressive faces** that **stays consistent** run-to-run. Free options first. Once you pick a
> winner, it's a one-line swap into the pipeline (`tools/studio_poc.py` image provider).

## The test prompts (copy these)

**Prompt A — calm face (style + gentle expression):**
```
A minimalist 2D cartoon illustration in a hand-drawn explainer-animation style. A single
stick-figure caveman with a round off-white head and a simple expressive face (two dot eyes,
eyebrows, a small calm line-mouth smile), thin black stick limbs, thick hand-drawn black
outlines, flat muted colors, no shading. He is stretching as he wakes up at dawn inside a
simple cave. Simple minimal background. No text, no words.
```

**Prompt B — strong emotion (your reference scene; tests expressive range):**
```
A minimalist 2D cartoon illustration, hand-drawn explainer style. A stick-figure office worker
with a round off-white head and a tired, stressed, worried expression (dot eyes, angled
eyebrows, a downturned line mouth), wearing a simple flat-colored suit, carrying a briefcase
and coffee cup, thin black stick limbs, thick black outlines, flat muted colors, no shading,
walking across a busy crosswalk with other stick-figure commuters, simple cartoon cars and
buildings behind. No text, no words.
```

> **Consistency test:** run Prompt A **3–4 times** in each tool. The winner is the one that keeps the
> *same character + style* each time.

---

## 1. Pollinations — easiest, 30 seconds, no signup ✅ start here
- **URL:** https://pollinations.ai  (or the direct image URL below)
- **Free?** 100% free, no account.
- **Steps (fastest = direct URL):**
  1. Open a browser tab.
  2. Paste this, with your prompt after `/prompt/`:
     `https://image.pollinations.ai/prompt/PROMPT_HERE?width=1920&height=1080&model=flux&seed=1`
  3. Press **Enter** → image loads (~10s).
  4. Change `seed=1` → `seed=2`, `3`… to get variations (same seed = same image).
- **Specific style setting:** none — the style lives **in the prompt** + `model=flux`. (Add `&nologo=true` after making a free account to drop the watermark.)
- **My opinion:** great instant gut-check. FLUX leans photoreal, so the look won't be as flat/clean as Recraft. Use it to sanity-check the prompt, not to pick the final style.

## 2. Recraft — ⭐ best for this flat-cartoon look
- **URL:** https://www.recraft.ai
- **Free?** **~30 generations/day** free (free output is public/non-commercial — fine for testing).
- **Steps:**
  1. Go to the site → **Sign up** (Google login is fastest) → the **canvas/editor** opens.
  2. Find the **prompt bar** (bottom). Above it, click the **Style** button.
  3. In the Style picker, **search a keyword**: try **`hand-drawn`**, then **`bold sketch`**, then **`cartoon`** — these live under the **Digital Illustration / Vector Illustration** groups. Pick a flat one.
  4. Paste **Prompt A** → **Generate**. Repeat with another style to compare.
- **Specific style setting:** **Style → "Hand-drawn"** (or **"Bold Sketch"** / a **Vector Illustration** cartoon style). For the real lock later: **Create style → upload 3–5 reference images** → it reuses that exact look on every generation (this is the consistency winner).
- **My opinion:** **my #1 pick.** It's the only tool built for flat/vector illustration — cleanest outlines and flat color, and the custom-style feature is exactly how you keep ~70 images consistent. Try this first.

## 3. Google AI Studio (Gemini 2.5 Flash Image / "Nano Banana") — free, best at faces
- **URL:** https://aistudio.google.com
- **Free?** Yes, up to a daily limit: **web UI ~500–1000 imgs/day**, **API ~500 req/day** (Flash Image, resets midnight UTC, no card). Over the quota → **~$0.039/img**. ≈ 8+ videos/day free at 60 imgs each. (Limits change — verify on signup; free-tier data may be used by Google.)
- **Steps:**
  1. Go to the site → **Sign in** with a Google account.
  2. Click **Create Prompt** / **＋ New chat**.
  3. Top-right **model dropdown** → choose **"Gemini 2.5 Flash Image"** (the image one, a.k.a. *Nano Banana*).
  4. Paste **Prompt A** → click **Run (▶)**.
  5. To refine, just type a follow-up: *"make the eyebrows more worried"* / *"flatter colors, thicker outlines"* → Run again.
- **Specific style setting:** none — it's **prompt-driven**, but it *follows* style/expression instructions better than most, and you can edit conversationally.
- **My opinion:** **strong #2.** Best for dialing in **facial expressions** and quick edits; huge free quota. Slightly less "vector-flat" than Recraft, but very controllable.

## 4. Cloudflare Workers AI — free, the future automation engine
- **URL:** https://playground.ai.cloudflare.com
- **Free?** Very generous free tier (~100k requests/day via API); no watermark.
- **Steps:**
  1. Go to the playground → sign in (free Cloudflare account if prompted).
  2. In the **model list**, select the image model **`@cf/black-forest-labs/flux-1-schnell`**.
  3. Paste **Prompt A**, and **append** ` , flat 2D, no realism, no 3D, no gradients` (FLUX drifts photoreal).
  4. Click **Run**.
- **Specific style setting:** none — style is the **prompt** (with the anti-realism nudge). Same FLUX model we'd call via API.
- **My opinion:** **best free option for automation later** (real API, massive free allowance). For the *look*, it won't beat Recraft without a trained style LoRA — but it's the cheapest way to run the finished pipeline.

## 5. Ideogram — clean illustration fallback
- **URL:** https://ideogram.ai
- **Free?** Limited free tier.
- **Steps:**
  1. Go to the site → **Sign in** (Google).
  2. Click the **prompt box** → a row of tabs appears at the bottom → click the **Style** tab.
  3. Choose **"Design"** (best for flat/graphic) — or **"Auto"** to let it decide.
  4. Paste **Prompt A** → **Generate** (returns 4 images).
- **Specific style setting:** **Style → "Design"** (flat/graphic) or **"General"**.
- **My opinion:** solid, especially if you ever need readable **text** in an image. Decent flat cartoon, but free tier is stingy — a fallback, not the front-runner.

---

## How to decide (≈10 min)
1. Run **Prompt A** in **Recraft (Hand-drawn style)**, **Gemini**, and **Pollinations**.
2. Generate each **3–4×** → judge on **(a) flat stick-figure look** and **(b) consistency across runs**.
3. Run **Prompt B** to check **expression range** (worried vs calm faces).
4. Pick the winner → tell me which → I wire it into the pipeline (and we lock the style with a fixed
   seed, then a trained **Recraft custom style** or **FLUX LoRA**).

**My prediction:** **Recraft for quality/consistency**, **Cloudflare-FLUX for free automation at scale.**
Trust your eyes though — outputs vary more than the marketing.

## Sources
- [Recraft styles (Hand-drawn / Bold Sketch / vector groups)](https://www.recraft.ai/blog/cartoon-vector-art) · [Recraft custom style](https://www.recraft.ai/docs/recraft-studio/styles/custom-styles/how-to-create-a-custom-style)
- [Ideogram style tab (General/Design/Realistic)](https://docs.ideogram.ai/using-ideogram/ideogram-features/style)
- [Pollinations API params (model/seed/nologo)](https://github.com/pollinations/pollinations/blob/main/APIDOCS.md)
- [Cloudflare Workers AI free image API](https://github.com/dotusmanali/Cloudflare-Image-Worker) · [Gemini image free tier](https://www.aifreeapi.com/en/posts/gemini-image-generation-free-api)
