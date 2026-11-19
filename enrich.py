#!/usr/bin/env python3
"""Apply the landing-page/per-standard enrichment to existing harvested data.

A full `scrape.py` run does this too. This script avoids repeating the
thousands of requests already completed.
"""

from __future__ import annotations

import json
from pathlib import Path

import atomic

import scrape

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "subjects.json"


def main() -> int:
    payload = json.loads(DATA.read_text(encoding="utf-8"))  # malformed data fails loudly
    total = len(payload["subjects"])
    for i, subject in enumerate(payload["subjects"], 1):
        print(f"[{i:2d}/{total}] {subject['slug']}", flush=True)
        if not subject.get("url"):
            print("  ! already pruned; run scrape.py first")
            continue
        html = scrape.fetch(subject["url"])
        if html:
            scrape.enrich_subject(subject, html)
        else:
            print(f"  ! failed: {subject['url']}")

    # Make sure failures from this pass are carried into the payload too.
    existing = payload.get("fetch_errors", [])
    payload["fetch_errors"] = existing + [e for e in scrape.FETCH_ERRORS if e not in existing]
    atomic.write(DATA, json.dumps(payload, indent=1, ensure_ascii=False))

    stds = sum(len(s["levels"][l]["standards"]) for s in payload["subjects"] for l in ("1", "2", "3"))
    print(f"\nstandards: {stds}, fetch errors: {len(payload['fetch_errors'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
