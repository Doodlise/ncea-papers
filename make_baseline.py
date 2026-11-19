#!/usr/bin/env python3
"""Refresh data/baseline.json from the current verified data.

Run this deliberately when NZQA legitimately removes or renames a standard
and verify.py reports a baseline regression. Never run it just to silence an
unexplained failure — investigate first.
"""

from __future__ import annotations

import json
from pathlib import Path

import atomic

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "subjects.json"
BASE = ROOT / "data" / "baseline.json"


def main() -> int:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    subjects = payload["subjects"]
    baseline = {
        "generated": payload.get("generated", "")[:10],
        "subjects": sorted(s["slug"] for s in subjects),
        "standards": sorted(
            [s["slug"], lvl, std["number"]]
            for s in subjects
            for lvl in ("1", "2", "3")
            for std in s["levels"][lvl]["standards"]
        ),
    }
    atomic.write(BASE, json.dumps(baseline, indent=1))
    print(f"baseline refreshed: {len(baseline['subjects'])} subjects, {len(baseline['standards'])} standards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
