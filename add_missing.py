#!/usr/bin/env python3
"""Add subjects/resources the main scrape missed.

- Subjects whose external assessments have schedules but no exam PDF
  (Design and Visual Communication, Technology, Visual Arts).
- Recently published files that postdate the last scrape.

All files are fetched from NZQA and live-checked before inclusion.
Run after focus.py, before build.py.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

import fix_and_prune
import focus
import scrape

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "subjects.json"
REPORT = ROOT / "data" / "link_report.json"

MISSING = {
    "design-and-visual-communication": ("Design and Visual Communication", {
        "1": ["92002", "92003"],
        "2": ["91337", "91338", "91339"],
        "3": ["91627", "91631"],
    }),
    "technology": ("Technology", {
        "2": ["91358", "91359", "91360", "91363"],
        "3": ["91612", "91613", "91614", "91617"],
    }),
    "visual-arts": ("Visual Arts", {
        "1": ["91914", "91915"],
        "2": ["91320", "91321", "91322", "91323", "91324"],
        "3": ["91455", "91456", "91457", "91458", "91459"],
    }),
    "litnum": ("Literacy and Numeracy", {"1": ["32403", "32405", "32406"]}),
    "cook-islands-maori": ("Cook Islands Māori", {
        "2": ["91113", "91116"], "3": ["91538", "91541"],
    }),
    "gagana-tokelau": ("Gagana Tokelau", {"1": ["92349", "92350"]}),
    "lea-faka-tonga": ("Lea Faka-Tonga", {
        "1": ["92038", "92039"], "2": ["91674", "91677"], "3": ["91679", "91682"],
    }),
    "te-reo-maori-kuki-airani": ("Te Reo Māori Kūki ‘Āirani", {"1": ["92042", "92043"]}),
    "vagahau-niue": ("Vagahau Niue", {"1": ["92353", "92354"]}),
}

# Files published after the last full scrape.
EXTRA = {
    "korean": {"2": ["91138", "91141"]},
    "art-history": {"2": ["91181"]},
}


OBSERVED_STATUS: dict[str, int] = {}


def live_pdf(url: str) -> int:
    """Return the observed HTTP status when it is a live PDF, else 0."""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-4"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status in (200, 206) and resp.read(5).startswith(b"%PDF"):
                    OBSERVED_STATUS[url] = resp.status
                    return resp.status
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return 0
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", 0)
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            if code == 0 or code in (403, 429, 500, 502, 503, 504):
                scrape.FETCH_ERRORS.append(f"{url}: {exc}")
    return 0


def detail_meta(html: str) -> tuple[str, str]:
    """Real standard title and credits from the NZQA detail page."""
    soup = scrape.soup_of(html)
    title = ""
    for h in soup.find_all("h3"):
        t = scrape.clean(scrape.text(h))
        if t and not t.startswith("Search ") and t != "Viewing documents":
            title = t
            break
    credits = ""
    for tr in soup.find_all("tr"):
        cells = [scrape.clean(scrape.text(c)) for c in tr.find_all(["td", "th"], recursive=False)]
        if cells and cells[0].startswith("Credits:") and len(cells) > 1:
            parts = cells[1].split()
            credits = parts[0] if parts else ""
            break
    return title, credits


def standards_for(name: str, levels: dict[str, list[str]]) -> list[tuple[str, str, dict]]:
    out = []
    for lvl, numbers in levels.items():
        for number in numbers:
            url = f"https://www.nzqa.govt.nz/ncea/assessment/view-detailed.do?standardNumber={number}"
            html = scrape.fetch(url)
            if not html:
                msg = f"detail page unavailable for hardcoded standard {number} ({name})"
                print("  ! " + msg)
                scrape.FETCH_ERRORS.append(msg)
                continue
            docs = []
            for d in scrape.collect_docs(html):
                d["type"] = focus.classify(d)
                d["url"] = fix_and_prune.fix_host(d["url"])
                if d["type"] in focus.KEEP_TYPES and live_pdf(d["url"]):
                    docs.append(d)
            if not docs:
                msg = f"no live papers for hardcoded standard {number} ({name})"
                print("  ! " + msg)
                scrape.FETCH_ERRORS.append(msg)
                continue
            title, credits = detail_meta(html)
            out.append((lvl, number, {
                "number": number,
                "subject": name,
                "title": title or "External assessment schedules",
                "credits": credits,
                "assessment": "External",
                "documents": docs,
            }))
    return out


def litnum_standards() -> list[tuple[str, str, dict]]:
    """LitNum papers/schedules are listed on the subject page, not detail pages."""
    by_number: dict[str, list[dict]] = {}
    # Each page is per standard; attribute by page, not by filename, so
    # descriptive filenames (e.g. "Literacy-Reading-...-assessment-paper")
    # are not skipped.
    for number in ("32403", "32405", "32406"):
        url = f"https://www2.nzqa.govt.nz/ncea/subjects/past-exams-and-exemplars/litnum/{number}/"
        html = scrape.fetch(url)
        if not html:
            msg = f"LitNum page unavailable for standard {number}"
            print("  ! " + msg)
            scrape.FETCH_ERRORS.append(msg)
            continue
        seen = {d["url"] for d in by_number.get(number, [])}
        for d in scrape.collect_docs(html):
            if d["url"] in seen:
                continue
            # LitNum translation papers (Niuean) are not English-medium exams.
            if re.search(r"-nex-|niuean|niue-|cook.?island|tokelau|samoan|gagana|faka|te.?reo", d["url"], re.I):
                continue
            d["type"] = focus.classify(d)
            d["url"] = fix_and_prune.fix_host(d["url"])
            if d["type"] in focus.KEEP_TYPES and live_pdf(d["url"]):
                by_number.setdefault(number, []).append(d)
                seen.add(d["url"])
    out = []
    for number, docs in by_number.items():
        detail = scrape.fetch(f"https://www.nzqa.govt.nz/ncea/assessment/view-detailed.do?standardNumber={number}")
        title, credits = detail_meta(detail) if detail else ("", "")
        out.append(("1", number, {
            "number": number,
            "subject": "Literacy and Numeracy",
            "title": title or "External assessment",
            "credits": credits,
            "assessment": "External",
            "documents": docs,
        }))
    return out


def add_standards(subject: dict, found: list[tuple[str, str, dict]]) -> list[str]:
    added_urls = []
    for lvl, number, std in found:
        bucket = subject["levels"][lvl]["standards"]
        existing = next((s for s in bucket if s["number"] == number), None)
        if existing:
            if existing.get("title") in (None, "", "External assessment schedules", "External assessment") or not existing.get("credits"):
                detail = scrape.fetch(
                    f"https://www.nzqa.govt.nz/ncea/assessment/view-detailed.do?standardNumber={number}"
                )
                if detail:
                    title, credits = detail_meta(detail)
                    if title:
                        existing["title"] = title
                    if credits:
                        existing["credits"] = credits
            seen = {d["url"] for d in existing["documents"]}
            for d in std["documents"]:
                if d["url"] not in seen:
                    existing["documents"].append(d)
                    seen.add(d["url"])
                    added_urls.append(d["url"])
        else:
            bucket.append(std)
            added_urls.extend(d["url"] for d in std["documents"])
    if found:
        subject["has_past_paper"] = True
    return added_urls


def main() -> int:
    payload = json.loads(DATA.read_text(encoding="utf-8"))  # malformed data fails loudly
    err_before = len(scrape.FETCH_ERRORS)
    by_slug = {s["slug"]: s for s in payload["subjects"]}
    added_urls: list[str] = []
    added_subjects = 0

    for slug, (name, levels) in MISSING.items():
        if slug == "litnum":
            found = litnum_standards()
            if not found:
                continue
            subject = by_slug.get(slug)
            if subject:
                added_urls.extend(add_standards(subject, found))
            else:
                subject = {
                    "slug": slug, "name": name, "has_past_paper": False,
                    "levels": {str(n): {"standards": []} for n in (1, 2, 3)},
                }
                added_urls.extend(add_standards(subject, found))
                payload["subjects"].append(subject)
                by_slug[slug] = subject
                added_subjects += 1
            continue
        # Always re-fetch: add_standards() dedupes by URL, so an incremental
        # run can still pick up newly published PDFs under known standards.
        found = standards_for(name, levels)
        if not found:
            msg = f"no papers found for hardcoded subject {slug} — check network / NZQA layout"
            print("  ! " + msg)
            scrape.FETCH_ERRORS.append(msg)
            continue
        if slug in by_slug:
            added_urls.extend(add_standards(by_slug[slug], found))
        else:
            subject = {
                "slug": slug,
                "name": name,
                "has_past_paper": False,
                "levels": {str(n): {"standards": []} for n in (1, 2, 3)},
            }
            added_urls.extend(add_standards(subject, found))
            payload["subjects"].append(subject)
            by_slug[slug] = subject
            added_subjects += 1

    for slug, levels in EXTRA.items():
        subject = by_slug.get(slug)
        if not subject:
            continue
        added_urls.extend(add_standards(subject, standards_for(subject["name"], levels)))

    payload["subjects"].sort(key=lambda s: s["name"].lower())

    new_errs = scrape.FETCH_ERRORS[err_before:]
    if new_errs:
        payload["fetch_errors"] = list(dict.fromkeys(payload.get("fetch_errors", []) + new_errs))
        print(f"  ! {len(new_errs)} fetch error(s) in add_missing; verify will fail")

    # Keep the link-verification report in sync with newly added URLs.
    if REPORT.exists():
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        report.setdefault("statuses", {}).update(
            {u: OBSERVED_STATUS.get(u, 0) for u in added_urls}
        )
        report["dead"] = [u for u in report.get("dead", []) if u not in added_urls]
        # Scope the report to the URLs that actually ship after focus().
        final_urls = {
            d["url"] for s in payload["subjects"] for l in ("1", "2", "3")
            for std in s["levels"][l]["standards"] for d in std["documents"]
        }
        report["statuses"] = {u: v for u, v in report["statuses"].items() if u in final_urls}
        REPORT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    if "focus_report" in payload:
        payload["focus_report"].update({
            "subjects_after": len(payload["subjects"]),
            "standards": sum(len(s["levels"][l]["standards"]) for s in payload["subjects"] for l in ("1", "2", "3")),
            "papers_and_schedules": sum(len(st["documents"]) for s in payload["subjects"]
                                        for l in ("1", "2", "3") for st in s["levels"][l]["standards"]),
        })
    DATA.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"added {added_subjects} subjects, {len(added_urls)} new PDFs; total {len(payload['subjects'])} subjects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
