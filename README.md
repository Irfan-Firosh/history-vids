# Faceless AI History — video pipeline

Automated **faceless "ancient humans / existential history"** YouTube channel — narration-driven
AI-image explainers. Reverse-engineered from **Axen (@AxenCool)**. Pipeline:

```
LLM script → style-locked Gemini images (Nano Banana, ref-conditioned) → static hard-cut assembly (1 image / ~5–10s beat) → Cartesia narration → FFmpeg concat
```

Static images, **hard cuts** (no transitions/motion); Gemini is used for **images only**. Runs end-to-end with real images+voice; ~90% automatable, ~$2.30/video.

## Quickstart (Tier-0 PoC)
```bash
uv sync                          # deps: pydantic, pillow, httpx, python-dotenv, matplotlib
uv run pytest                    # studio unit tests (27)
python tools/studio_poc.py       # → result/axen/poc/sample.mp4 (free: placeholder images + macOS `say`)

# Real pipeline (needs .env: GEMINI_API_KEY + billing, CARTESIA_* set):
python tools/make_refs.py        # once: bootstrap assets/refs/ (REF-1 character + REF-2 expressions)
python tools/studio_poc.py --images gemini --voice cartesia   # → result/axen/poc/sample_gemini.mp4
```
ffmpeg + ffprobe on PATH required. Optional object storage: `docker compose -f docker/docker-compose.yml up -d` (MinIO).

## Folder layout
```
.
├── README.md                  this file
├── CLAUDE.md                  the persistent contract / project brief
├── TASKS.md                   task board (current phase + checklist)
├── pyproject.toml             minimal deps (pydantic · pillow · httpx · python-dotenv · matplotlib)
├── .env                       secrets (GEMINI_API_KEY, CARTESIA_*) — gitignored, preserved
│
├── studio/                    ◀ the pipeline's pure logic (importable package)
│   ├── types.py               Scene (+ shot_type) / Storyboard models + provider Protocols
│   ├── style.py               LOCKED_STYLE + palette (consistency = ref conditioning, see gemini.py)
│   ├── gemini.py              Gemini image API request-build + response-parse (pure, tested)
│   ├── kenburns.py            per-scene FFmpeg filter (static hard-cut default; optional Ken-Burns)
│   └── storyboard.py          canned demo storyboard (→ LLM-generated in production)
│
├── tools/
│   ├── studio_poc.py          ◀ runnable PoC: providers (PIL/Gemini/Say/Cartesia/FFmpeg) + orchestration
│   └── make_refs.py           bootstrap the REF-1/REF-2 reference sheets → assets/refs/
│
├── assets/refs/               channel identity: character.png + expressions.png — ⚠️ NOT present,
│                             regenerate via tools/make_refs.py and commit (see architecture.md)
│
├── tests/
│   └── test_studio.py         studio unit tests (27)
│
├── context/                   the knowledge base
│   └── project/               ◀ active spec: README · architecture · roadmap
│
├── result/                    research + generated artifacts
│   ├── axen/                  Axen reverse-eng (report.md, production_stack_research.md, charts)
│   │   └── poc/               generated PoC video + assets (gitignored, regenerable)
│   ├── report.md / charts/    NexLev "new high-earners" niche research
│   ├── data/channels.json     machine-readable channel data
│   └── generate_report.py     report generator
│
├── tasks/                     working notes (todo.md, lessons.md)
└── docker/
    └── docker-compose.yml     optional MinIO object storage (empty; Postgres/Redis removed)
```

## Status & next
Tier-0 runs end-to-end with **real Gemini images + Carson voice** (character-consistent across scenes).
**Phase 1 remaining:** LLM script (real-citation RAG) + thumbnail + fact-check/AIGC-disclosure QC →
first full ~7-min video. See `context/project/roadmap.md`.

> History: this repo previously hosted a Twitch-clip pipeline and a RankZilla Shorts scaffold — both
> abandoned, recoverable via git tags `twitch-clips-v1` and `titan-rankzilla-v1`.
