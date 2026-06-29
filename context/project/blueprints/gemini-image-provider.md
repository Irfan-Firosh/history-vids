# Blueprint — Gemini "Nano Banana" Image Provider

> The image stage of the Tier-0 pipeline, wired to **Gemini 2.5 Flash Image** with a
> reference-image workflow for character consistency. Replaces the old fal.ai/FLUX plan
> (fal had no free API credits; Gemini won the bake-off on style + consistency).
> Status: validated live (key + billing + 16:9 all confirmed) — implementing.

## Decision record
- **Winner = Gemini 2.5 Flash Image** (`gemini-2.5-flash-image`, "Nano Banana"). First-try output nailed
  the locked stick-figure style (round off-white head, dot eyes + eyebrows + line mouth, thick outlines,
  flat muted colors). `gemini-3.1-flash-image` is also live on the key → A/B later via `GEMINI_IMAGE_MODEL`.
- **API needs billing.** Free tier for image gen via API = **0** (the ~500/day free quota is AI-Studio
  *web UI* only). Pay-as-you-go / prepaid balance required. Validated working after top-up.
- **Transport = httpx + REST** (not the `google-genai` SDK) — zero new heavy deps, mirrors
  `CartesiaVoiceProvider`. Endpoint: `…/v1beta/models/{model}:generateContent?key=…`.

## Cost model
Flat **~1290 output tokens per image ≈ $0.039** (independent of prompt length / resolution ≤ ~1MP).
Input is negligible: prompt text ~$0.00004; each reference image ~$0.0004. So passing REF-1 + REF-2 on
every character shot costs <0.1¢/scene. **~60-image video ≈ $2.30–$2.40.** Bootstrapping refs once: a few ¢.

## Consistency strategy (the hard part)
The lever moves from *fixed-seed* (FLUX) to **reference conditioning** (Gemini's strength):
1. **REF-1 — character model sheet** (the identity anchor): the recurring stick-figure, neutral pose,
   plain bg. Passed on *every* character shot.
2. **REF-2 — expression sheet**: the same head ×6 (calm/worried/sad/surprised/angry/thoughtful) so the
   model matches emotion on-model. Passed on emotional character shots.
3. Per-scene prompt = subject + **explicit facial expression** + `LOCKED_STYLE`, written as an edit
   instruction ("the same character, now …, keep identical style/line-weight/colors").
Refs are **gitignored-free, committed** at `assets/refs/{character,expressions}.png` (channel identity →
must be reproducible). Generated from *our own* prompts (rights-clean), never scraped competitor frames.

## Aspect ratio
Request **16:9** via `generationConfig.imageConfig.aspectRatio` → native **1344×768** (validated). The
existing `scene_filter` `scale…force_original_aspect_ratio=increase,crop` still normalizes to 1920×1080,
so even a non-16:9 return is safe (fixes the earlier "screen gets cropped" worry).

## The seam change
Current `ImageProvider.generate(prompt, out_path)` carries **no references** → it must grow:
```python
def generate(self, prompt: str, out_path: Path, refs: Sequence[Path] = ()) -> Path: ...
```
- Backward compatible (`refs=()` default). `PlaceholderImageProvider` ignores `refs`.
- `Scene` gains `shot_type: Literal["character","wide","concept","map"] = "character"`.
  `shot_uses_character()` → `True` for `character`/`wide` (pass refs), `False` for `concept`/`map`
  (no refs — don't force a person into a prop/map shot).
- The PoC main loop computes per-scene `refs` from `shot_type` and the available `assets/refs/`.

## Code layout (pure logic in `studio/`, side effects in `tools/`)
| File | Role |
|---|---|
| `studio/gemini.py` *(new, pure)* | `endpoint()`, `build_request()`, `encode_image()`, `parse_image()`, `GeminiError` (`.is_billing`, `.is_retryable`). Unit-tested offline. |
| `studio/types.py` | `Scene.shot_type` (Literal) + `SHOT_TYPES`, `shot_uses_character()`; `ImageProvider.generate` gains `refs`. |
| `studio/storyboard.py` | `DEMO_STORYBOARD` scenes tagged with `shot_type`. |
| `tools/studio_poc.py` | `GeminiImageProvider` (httpx POST + retry/backoff, billing-aware error); `load_dotenv()`; `--images placeholder|gemini`; per-scene refs. |
| `tools/make_refs.py` *(new)* | Bootstrap REF-1 (text→image) then REF-2 (REF-1→edit) → `assets/refs/`. |
| `tests/test_studio.py` | +tests: `build_request`/`parse_image`/error flags, `shot_type` validation + `shot_uses_character`. |
| `pyproject.toml` | add `python-dotenv`; ruff per-file-ignore for `tools/make_refs.py`. |

## Error / quota handling
`parse_image` raises `GeminiError(code, status, message)`.
- `.is_billing` (message has "deplet"/"billing"/"free_tier"/"limit: 0") → **raise immediately** with a
  "top up at ai.studio/projects" hint; retrying is pointless.
- `.is_retryable` (429/500/503 and *not* billing) → exponential backoff, up to `max_retries=4`.
- No image part → `GeminiError("NO_IMAGE")` (e.g. safety refusal) → surfaced, not silently skipped.

## Test / verify strategy
- **Offline (no spend):** pure `studio/gemini.py` fns + `shot_type` (`/ecc:tdd`, RED→GREEN). `ruff` clean, full `pytest` green.
- **Live (needs billing):** `make_refs.py` → eyeball `assets/refs/`; then
  `python tools/studio_poc.py --images gemini --voice cartesia` → real video; **`/ecc:eval-harness`** to
  score cross-scene character consistency (same head/proportions/line-weight) + style adherence.

---

## Optimized execution prompt (`/ecc:prompt-optimize` output — reproducible handoff)

> Implement the Gemini image stage for the faceless-AI-history pipeline. Pure logic in `studio/`,
> side effects in `tools/`. TDD: write tests first, keep `ruff` (line-length 100) clean, full `pytest` green.
>
> 1. **`studio/gemini.py` (pure, new):** `GEMINI_API_BASE`, `DEFAULT_IMAGE_MODEL="gemini-2.5-flash-image"`,
>    `DEFAULT_ASPECT_RATIO="16:9"`; `endpoint(model,key)`; `build_request(prompt, ref_images_b64=(),
>    aspect_ratio="16:9")` → `{"contents":[{"parts":[{"text":…}, {"inlineData":{"mimeType":"image/png",
>    "data":b64}}…]}], "generationConfig":{"responseModalities":["IMAGE"],"imageConfig":{"aspectRatio":…}}}`
>    (omit `imageConfig` when `aspect_ratio is None`); `encode_image(bytes)->b64`; `parse_image(resp)->bytes`
>    raising `GeminiError(code,status,message)` with `.is_billing` / `.is_retryable`. Tolerate
>    `inlineData`/`inline_data`.
> 2. **`studio/types.py`:** `Scene.shot_type: Literal["character","wide","concept","map"]="character"`;
>    add `SHOT_TYPES` + `shot_uses_character()`; extend `ImageProvider.generate` with `refs: Sequence[Path]=()`.
> 3. **`studio/storyboard.py`:** tag each demo scene with a `shot_type`.
> 4. **`tools/studio_poc.py`:** `load_dotenv()`; `GeminiImageProvider` (reads `GEMINI_API_KEY`/
>    `GEMINI_IMAGE_MODEL`; httpx POST; billing→raise, transient→backoff×4); `PlaceholderImageProvider`
>    accepts+ignores `refs`; `--images placeholder|gemini` (default placeholder); per-scene
>    `refs = assets/refs/* if images=="gemini" and shot_uses_character(scene.shot_type)`.
> 5. **`tools/make_refs.py` (new):** bootstrap REF-1 then REF-2 → `assets/refs/`.
> 6. **Tests:** `build_request` (text-only / with refs / aspect None), `parse_image` (decode / api-error
>    billing flag / no-image / retryable), `Scene` default+invalid `shot_type`, `shot_uses_character`.
> 7. **Verify:** offline `ruff` + `pytest`; live `make_refs.py` + `--images gemini`; `/ecc:eval-harness`
>    for consistency scoring.
