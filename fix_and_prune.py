#!/usr/bin/env python3
"""Keep only live, direct PDF links.

1. Fix NZQA host mapping (/nqfdocs/ and /bin/ live on www, /assets/ on www2).
2. Drop every non-PDF link (pages, ZIPs, DOCs, login links).
3. Check every remaining PDF against NZQA and drop 404/dead links.
4. Drop empty standards/subjects and write a report.

Run after scrape.py / enrich.py, before build.py.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import scrape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "subjects.json"
REPORT = ROOT / "data" / "link_report.json"
UA = "Mozilla/5.0 (compatible; NCEA-papers-index/1.0)"
PDF = re.compile(r"\.pdf$", re.I)
WORKERS = 25


def fix_host(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    path = p.path
    host = p.netloc
    if path.startswith(("/nqfdocs/", "/bin/")):
        host = "www.nzqa.govt.nz"
    elif path.startswith("/assets/"):
        host = "www2.nzqa.govt.nz"
    return urllib.parse.urlunsplit(("https", host, path, p.query, ""))


def is_pdf(url: str) -> bool:
    return bool(PDF.search(urllib.parse.urlsplit(url).path))


def clean_name(name: str) -> str:
    name = name.strip()
    if " mō " in name:
        name = name.rsplit(" mō ", 1)[-1].strip()
    for marker in (" exemplars", " ngā aromatawai", " ngā tauaromahi"):
        idx = name.lower().find(marker)
        if idx > 0:
            name = name[:idx].strip()
    return name


def check(url: str) -> tuple[str, int | str]:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-7"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                head = resp.read(8)
                # The %PDF magic is the reliable signal; some servers serve
                # PDFs as application/octet-stream.
                if resp.status in (200, 206) and head.startswith(b"%PDF"):
                    return url, resp.status
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return url, "not-pdf"
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", 0)
            if code == 0 or code in (403, 429, 500, 502, 503, 504):
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                scrape.FETCH_ERRORS.append(f"{url}: {exc}")
            return url, code or str(exc)
    return url, "no-response"


def main() -> int:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    stats: Counter = Counter()

    def clean_docs(docs: list[dict]) -> list[dict]:
        out = []
        for d in docs:
            stats["docs_in"] += 1
            url = fix_host(d["url"])
            if not is_pdf(url):
                stats["dropped_non_pdf"] += 1
                continue
            d["url"] = url
            if url not in {x["url"] for x in out}:
                out.append(d)
        return out

    for s in payload["subjects"]:
        s["name"] = clean_name(s["name"])
        s.pop("url", None)  # HTML landing-page links are not PDFs
        for lvl in ("1", "2", "3"):
            info = s["levels"][lvl]
            for std in info["standards"]:
                std["documents"] = clean_docs(std["documents"])
                std.pop("detail_url", None)
            info["standards"] = [std for std in info["standards"] if std["documents"]]
            info.pop("links", None)

    # Subjects with no PDFs are removed entirely.
    before = len(payload["subjects"])
    payload["subjects"] = [
        s for s in payload["subjects"]
        if any(s["levels"][l]["standards"] for l in ("1", "2", "3"))
    ]
    stats["subjects_removed"] = before - len(payload["subjects"])

    # Collect every remaining PDF URL.
    urls: set[str] = set()
    for s in payload["subjects"]:
        for lvl in ("1", "2", "3"):
            info = s["levels"][lvl]
            for std in info["standards"]:
                urls.update(d["url"] for d in std["documents"])
    print(f"Checking {len(urls):,} PDF links with {WORKERS} workers...")
    statuses: dict[str, int | str] = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(check, u): u for u in urls}
        for i, future in enumerate(as_completed(futures), 1):
            u, code = future.result()
            statuses[u] = code
            if i % 1000 == 0:
                print(f"  {i:,}/{len(urls):,} checked", flush=True)

    codes = Counter(str(v) for v in statuses.values())
    print(f"Status codes: {dict(codes.most_common(10))}")

    def keep(d: dict) -> bool:
        return statuses.get(d["url"]) in (200, 206)

    dead: list[str] = []
    for s in payload["subjects"]:
        for lvl in ("1", "2", "3"):
            info = s["levels"][lvl]
            for std in info["standards"]:
                before_n = len(std["documents"])
                dead.extend(d["url"] for d in std["documents"] if not keep(d))
                std["documents"] = [d for d in std["documents"] if keep(d)]
                stats["dropped_dead"] += before_n - len(std["documents"])
            info["standards"] = [std for std in info["standards"] if std["documents"]]
    before = len(payload["subjects"])
    payload["subjects"] = [
        s for s in payload["subjects"]
        if any(s["levels"][l]["standards"] for l in ("1", "2", "3"))
    ]
    stats["subjects_removed_dead"] = before - len(payload["subjects"])

    # The full live URL check finishes here; that is the honest "last checked" date.
    payload["generated"] = datetime.now(timezone.utc).isoformat()
    payload["prune_report"] = dict(stats)
    payload["prune_report"]["urls_checked"] = len(urls)
    payload["prune_report"]["urls_live"] = sum(1 for v in statuses.values() if v in (200, 206))
    soft_failures = sum(1 for v in statuses.values() if v == "not-pdf")
    if urls and soft_failures / len(urls) > 0.01:
        scrape.FETCH_ERRORS.append(
            f"{soft_failures}/{len(urls)} live URLs returned non-PDF bodies — possible upstream incident"
        )
    if scrape.FETCH_ERRORS:
        payload["fetch_errors"] = list(dict.fromkeys(
            payload.get("fetch_errors", []) + scrape.FETCH_ERRORS
        ))
        print(f"  ! {len(scrape.FETCH_ERRORS)} transient link-check error(s) recorded")
    # Write the report first: a failure here leaves the source data untouched.
    REPORT.write_text(json.dumps({"statuses": {k: v for k, v in statuses.items()}, "dead": dead}, indent=1), encoding="utf-8")
    DATA.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"\nReport: {dict(stats)}")
    print(f"Live PDF URLs: {payload['prune_report']['urls_live']:,}/{len(urls):,}")
    print(f"Subjects left: {len(payload['subjects'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
