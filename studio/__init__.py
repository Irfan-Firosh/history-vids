"""`studio` — pure logic for the faceless AI-history video pipeline (Tier-0 PoC).

Stack: LLM script → style-locked images (Gemini, ref-conditioned) → static hard-cut FFmpeg
assembly → Cartesia narration. This package holds the **pure, testable** pieces (storyboard model,
locked style, scene-filter builder, Gemini request/parse). Side-effecting providers (image gen, TTS,
ffmpeg) live in `tools/studio_poc.py` behind the Protocols here, so they swap freely
(Placeholder→Gemini, Say→Cartesia) without touching logic.
"""

from __future__ import annotations

from studio import agnes, cloudflare, gemini, huggingface, llm
from studio.captions import cue_timings, split_caption_cues
from studio.kenburns import MOTIONS, scene_filter
from studio.narration import (
    align_beats,
    align_beats_to_words,
    build_transcript,
    caption_timeline,
    emphasis_timeline,
    frames_for_span,
    image_timeline,
)
from studio.research import ResearchProvider, ResearchSource, format_research_brief
from studio.run_log import RunManifest, RunRecorder, SceneRecord, new_run_id
from studio.storyboard import DEMO_STORYBOARD, storyboard_from_dict
from studio.style import CONCEPT_STYLE, LOCKED_STYLE, styled_prompt, thumbnail_prompt
from studio.types import (
    SHOT_TYPES,
    ImageProvider,
    Scene,
    Storyboard,
    VoiceProvider,
    shot_uses_character,
)

__all__ = [
    "Scene",
    "Storyboard",
    "ImageProvider",
    "VoiceProvider",
    "ResearchProvider",
    "ResearchSource",
    "format_research_brief",
    "LOCKED_STYLE",
    "CONCEPT_STYLE",
    "styled_prompt",
    "thumbnail_prompt",
    "MOTIONS",
    "scene_filter",
    "split_caption_cues",
    "cue_timings",
    "build_transcript",
    "align_beats",
    "align_beats_to_words",
    "caption_timeline",
    "emphasis_timeline",
    "image_timeline",
    "frames_for_span",
    "DEMO_STORYBOARD",
    "storyboard_from_dict",
    "SHOT_TYPES",
    "shot_uses_character",
    "agnes",
    "cloudflare",
    "gemini",
    "huggingface",
    "llm",
    "RunRecorder",
    "RunManifest",
    "SceneRecord",
    "new_run_id",
]
