# 03 — Voiceover → Cartesia TTS (Carson)

> Cartesia isn't "prompted" — you feed it the **voiceover text** + a **voice**. Take the `Voiceover:`
> lines from the 01 storyboard and turn them into narration.

## Config (already set)
- **Voice:** Carson — `CARTESIA_VOICE_ID = 86e30c1d-714b-4074-a1f2-1cb6b552fb49`
- **Key:** `CARTESIA_API_KEY` (in `.env`) · **Model:** Sonic (`sonic-2`)
- **Tone for this channel:** calm, warm, authoritative, unhurried (documentary narrator). Let the script
  carry the emotion; don't over-perform.

## Two ways to use it
**A) Quick / manual — Cartesia Playground**
1. Go to **https://play.cartesia.ai** → sign in.
2. Pick the **Carson** voice (or search the voice id above).
3. Paste the narration → **Generate** → **download the WAV**.
- Paste **per scene** (one clip each) if you want to assemble manually, or the **full script** for one track.

**B) Automatic — our pipeline (recommended)**
- `tools/studio_poc.py --voice cartesia` already calls Cartesia with Carson **per scene**, so each
  scene's image is held for exactly its narration length, then hard-cut to the next. Nothing to paste —
  it reads the storyboard. (This is why 01 outputs one `Voiceover:` line per scene.)

## Writing the narration well (do this in the 01 script)
- **Short, conversational sentences** — Sonic reads natural phrasing best; avoid long run-ons.
- **Punctuation = pacing** — periods and commas create natural pauses; use them deliberately.
- Spell tricky things phonetically if mispronounced (e.g. a name → how it sounds).
- Keep numbers speakable ("about fifteen hours", not "15h").
- One idea per scene; the last scene's line is the **mic-drop** payoff.

## Hand-off
- Per-scene `Voiceover:` lines → the pipeline (B) or the Playground (A).
- Scene image (from 02) is shown for the duration of that scene's audio → static, hard cut. That's the
  whole video: `image[i]` held for `len(voice[i])`, concatenated.
