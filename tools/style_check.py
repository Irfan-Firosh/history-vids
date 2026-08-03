#!/usr/bin/env python3
"""Fast style feedback loop: change LOCKED_STYLE, see the numbers in ~2 minutes.

  uv run python tools/style_check.py --probe            # 1 image
  uv run python tools/style_check.py --batch 12         # spread + contact sheet

Loads the reference envelope (numbers only, see context/project/style-envelope.json) and scores
freshly generated frames against it with `studio.style_metrics` (pure). This is the same
measurement the pre-flight gate in `tools/studio_poc.py::render_storyboard` runs automatically
before the main image loop -- this CLI exists to iterate on `LOCKED_STYLE` interactively without
spinning up a whole run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from studio.style import LOCKED_STYLE, styled_prompt  # noqa: E402
from studio.style_metrics import Envelope, conforms, measure_frame  # noqa: E402
from studio.types import SHOT_TYPES  # noqa: E402

ENVELOPE_PATH = _ROOT / "context" / "project" / "style-envelope.json"
_SUBJECTS = (
    "two early humans crouched by a fire at night",
    "a wide empty tundra under a pale sky",
    "a hand axe and scattered bone fragments",
    "a simple map of a river valley",
)


def load_envelope() -> Envelope:
    """The measured reference envelope (see ENVELOPE_PATH's `_provenance` for the calibration
    story -- numbers only, never competitor media)."""
    raw = json.loads(ENVELOPE_PATH.read_text())
    return Envelope(
        saturation=tuple(raw["saturation"]),
        colour_bins=tuple(raw["colour_bins"]),
        near_white_pct=tuple(raw["near_white_pct"]),
    )


def check(paths: list[Path], envelope: Envelope) -> bool:
    """Measure every frame at `paths` against `envelope`, print a PASS/FAIL line + failure
    reasons for each, and return whether ALL of them conform."""
    all_ok = True
    for p in paths:
        m = measure_frame(np.asarray(Image.open(p).convert("RGB")))
        ok, failures = conforms(m, envelope)
        all_ok = all_ok and ok
        print(f"{'PASS' if ok else 'FAIL'}  {p.name}  sat={m.saturation} bins={m.colour_bins} "
              f"white={m.near_white_pct}%")
        for f in failures:
            print(f"        - {f}")
    return all_ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", action="store_true", help="one image")
    ap.add_argument("--batch", type=int, default=0, help="N images across shot types")
    ap.add_argument("--out", type=Path, default=_ROOT / "result" / "style_check")
    args = ap.parse_args()

    from tools.studio_poc import (
        make_image_provider,  # noqa: PLC0415 - avoids import cost when unused
    )

    provider = make_image_provider("agnes")
    args.out.mkdir(parents=True, exist_ok=True)
    n = 1 if args.probe else max(args.batch, 1)
    paths: list[Path] = []
    for i in range(n):
        subject = _SUBJECTS[i % len(_SUBJECTS)]
        shot = SHOT_TYPES[i % len(SHOT_TYPES)]
        target = args.out / f"probe_{i:02d}_{shot}.png"
        provider.generate(styled_prompt(subject, LOCKED_STYLE, shot_type=shot), target)
        paths.append(target)
    sys.exit(0 if check(paths, load_envelope()) else 1)


if __name__ == "__main__":
    main()
