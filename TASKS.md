# Task Board — Faceless AI History Channel

> Claude Code reads this first every session. Keep one item `<- ACTIVE`.
> Spec: `context/project/` (README · architecture · roadmap) · research: `result/axen/`.

## Current phase: Tier-0 PoC ✅ → Phase 1 (first real video)

### Done
- [x] Reverse-engineer **Axen / @AxenCool** + production-stack research → `result/axen/`
- [x] **Tier-0 PoC** — `studio/` (Scene/Storyboard, locked style, scene filter — static hard-cut; 15 tests) +
      `tools/studio_poc.py` → `result/axen/poc/sample.mp4` (script→images→static hard-cut→voice→assemble; free + offline)
- [x] Repo cleanup — deleted old Twitch/RankZilla code (tags `twitch-clips-v1`, `titan-rankzilla-v1`);
      slimmed to `studio/` + context + research; MinIO-only docker (emptied)

### Phase 1 — first real, publishable video (see context/project/roadmap.md)  <- ACTIVE
- [ ] produce ONE full 6-9 min Agnes+Cartesia video (real live render, ~15-30 min) at quality ≥ the clone swarm
- [ ] **Thumbnail** generator + title from the hook
- [ ] **QC gate** — fact-check citations + AIGC-disclosure flag
- [ ] produce ONE full ~5-min video at quality ≥ the clone swarm

### Open inputs needed
- ✅ Carson `CARTESIA_VOICE_ID`, ✅ **Gemini** billing, ✅ **LLM_API_KEY**+**EXA_API_KEY**, ✅ **HUGGINGFACE_TOKEN** — all set + validated.
- Decided: **Gemini** (character, ref-conditioned) + **HuggingFace FLUX** (free, non-character/cutaways); static hard cuts, no AI-motion.
