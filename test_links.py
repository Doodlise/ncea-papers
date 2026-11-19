#!/usr/bin/env python3
"""Independent live test: sample PDFs from the FINAL data and fetch them."""

from __future__ import annotations

import json
import os
import random
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "subjects.json"


def main() -> int:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    docs = []
    for s in payload["subjects"]:
        for lvl in ("1", "2", "3"):
            info = s["levels"][lvl]
            for std in info["standards"]:
                docs.extend((s["name"], lvl, d) for d in std["documents"])
    seed = os.environ.get("LINK_SAMPLE_SEED")
    if seed is None:
        seed = str(random.SystemRandom().randrange(2 ** 32))  # rotate each run
    random.seed(seed)
    sample = random.sample(docs, min(30, len(docs)))
    ok = 0
    for subject, lvl, d in sample:
        url = d["url"]
        good, ctype = False, "-"
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-4"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    head = resp.read(5)
                    ctype = resp.headers.get("Content-Type", "")
                    good = resp.status in (200, 206) and head.startswith(b"%PDF")
                if good:
                    break
            except Exception as exc:  # noqa: BLE001
                ctype = str(exc)
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
        if good:
            ok += 1
        print(f"{'PASS' if good else 'FAIL'} | L{lvl} {subject[:22]:22} | {ctype[:22]:22} | {url[-58:]}")
    print(f"\n{ok}/{len(sample)} sampled PDFs open correctly (seed={seed}; replay with LINK_SAMPLE_SEED={seed})")
    return 0 if ok == len(sample) else 1


if __name__ == "__main__":
    raise SystemExit(main())
