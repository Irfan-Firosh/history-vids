"""Replay the rubric over real corpora before trusting it to block runs.

Pass criteria: every measured WINNER passes, the measured UNDERPERFORMER fails. If a threshold
rejects a 996K-view script, the threshold is wrong — not the script.

This is the "calibrate, then enforce" half of the script-craft gate (see
`context/research/2026-08-01/05-script-craft.md` §5/§13 and `tasks/lessons.md` 2026-08-03). It reads
whatever corpora actually exist on disk: this repo's own generated scripts under `result/*/scripts`
(storyboard.json files), and/or a directory of competitor transcripts (plain .txt). It does NOT
fabricate a corpus — if nothing is found, it says so plainly rather than inventing transcripts, per
`tasks/lessons.md`'s "a threshold you haven't replayed is a guess" rule. When no transcripts are on
disk, calibrate by hand against the published per-video metrics in the research doc instead.

Usage:
    uv run python tools/calibrate_rubric.py result/axen/scripts /path/to/transcripts
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio.script_rubric import score_script  # noqa: E402


def _narrations(path: Path) -> list[str]:
    if path.suffix == ".json":
        data = json.loads(path.read_text())
        return [s.get("narration", "") for s in data.get("scenes", []) if isinstance(s, dict)]
    return [path.read_text()]


def main() -> None:
    roots = [Path(a) for a in sys.argv[1:]] or [Path("result/axen/scripts")]
    files: list[Path] = []
    for root in roots:
        files += sorted(root.rglob("storyboard.json")) + sorted(root.rglob("*.txt"))
    if not files:
        print(f"no corpus found under {[str(r) for r in roots]} — nothing to replay.")
        print("Calibrate by hand against the published per-video metrics instead; see")
        print("context/research/2026-08-01/05-script-craft.md §5/§13 and tasks/lessons.md.")
        return
    passed = 0
    for f in files:
        report = score_script(_narrations(f))
        mark = "PASS" if report.ok else "FAIL"
        passed += report.ok
        print(f"{mark}  {f}\n      {report.summary()}")
        for failure in report.failures:
            print(f"        - {failure}")
    print(f"\n{passed}/{len(files)} passed")


if __name__ == "__main__":
    main()
