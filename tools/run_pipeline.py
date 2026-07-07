#!/usr/bin/env python3
"""Whole-pipeline orchestrator for the dashboard: topic → script (Exa+LLM) → render, one run record.

Creates the run up front (so the dashboard shows research progress live), generates the script + Exa
sources, attaches them to the run, then renders — all into the same RunRecorder, so the manifest
carries the full pipeline (topic, script, sources, scene images, video, log).

Run:  python tools/run_pipeline.py --topic "..." --run-id <id> --images gemini --voice cartesia
Needs: LLM_API_* + EXA_API_KEY (script) and, for real media, GEMINI_API_KEY + CARTESIA_* in .env.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402

from studio import RunRecorder, new_run_id, storyboard_from_dict  # noqa: E402
from tools.make_script import build_and_save  # noqa: E402
from tools.studio_poc import (  # noqa: E402
    IMAGE_PROVIDER_NAMES,
    RUNS_DIR,
    CartesiaVoiceProvider,
    SayVoiceProvider,
    attach_script_artifacts,
    build_providers,
    providers_from_roles,
    render_storyboard,
)


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True)
    ap.add_argument("--min-minutes", type=float, default=6.0)  # target duration band (6-9 min)
    ap.add_argument("--max-minutes", type=float, default=9.0)
    ap.add_argument("--scenes", type=int, default=None, help="override the beat count (else derived)")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--images", choices=list(IMAGE_PROVIDER_NAMES), default="placeholder",
                    help="shorthand: pick a legacy provider mix for all image roles")
    ap.add_argument("--char-model", choices=list(IMAGE_PROVIDER_NAMES))
    ap.add_argument("--concept-model", choices=list(IMAGE_PROVIDER_NAMES))
    ap.add_argument("--voice", choices=["say", "cartesia"], default="say")
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--review", action="store_true",
                    help="pause after images for human review/approval before assembling")
    args = ap.parse_args()

    if args.char_model or args.concept_model:  # per-role selection
        images = providers_from_roles(
            args.char_model or args.images, args.concept_model or args.images
        )
        images_label = f"{images.character.name}/{images.concept.name}"
    else:
        images = build_providers(args.images)
        images_label = args.images
    voice = CartesiaVoiceProvider() if args.voice == "cartesia" else SayVoiceProvider()

    rec = RunRecorder.create(
        RUNS_DIR,
        title=args.topic,
        images_provider=images_label,
        voice_provider=voice.name,
        scene_count=0,
        run_id=args.run_id or new_run_id(),
    )
    rec.attach_artifacts(topic=args.topic)
    print(f"Run: {rec.run_id} → researching {args.topic!r}")

    try:
        out_dir = build_and_save(
            args.topic, args.scenes, args.min_minutes, args.max_minutes, log=rec.log
        )
    except Exception as exc:
        rec.failed(exc)
        print(f"❌ script generation failed: {exc}", file=sys.stderr)
        raise

    attach_script_artifacts(rec, out_dir / "storyboard.json")
    sb = storyboard_from_dict(json.loads((out_dir / "storyboard.json").read_text()))
    rec.set_plan(title=sb.title, scene_count=len(sb.scenes))
    render_storyboard(
        rec, sb, images, voice, captions=not args.no_captions, pause_for_review=args.review,
    )


if __name__ == "__main__":
    main()
