# Lessons

## 2026-06-27 — Verify the premise with real data before designing
**Pattern:** The brief assumed RankZilla was a "ranking/#1-reveal" channel; real recon showed it's a
single-hook machine (96% identical title). Pulling genuine data first (yt-dlp flat-playlist) prevented
designing the wrong system. Always ground reverse-engineering in observed data; mark modeled vs observed.

## 2026-06-27 — The goal is YouTube Shorts; stop defaulting to Twitch
**Correction:** I repeatedly proposed running Twitch discovery / labeling Twitch candidates as the
next step (e.g., to make `/eval` produce a verdict). The user pushed back: the project goal is the
autonomous **YouTube Shorts** business; **Twitch is legacy/decommission-only**, not a workflow to run.
**Rule:** Frame every "next step" around the **active spec** (now `context/project/`), never around an
abandoned/legacy engine. Don't route progress back through legacy code (Twitch, reranking). When blocked,
solve it within the active direction or name the real blocker. See [[titan-project-goal]].
(Update 2026-06-27: niche later settled on faceless AI-history; old Twitch/RankZilla code deleted, tagged.)

