#!/usr/bin/env python3
"""Harvest the official NZQA index of NCEA past papers and assessment resources.

Stages
------
1. Read the master subject index and every subject landing page.
2. For each subject x level, read NZQA's exam, report and specification
   search results and extract every achievement standard.
3. For each standard, read its "View all documents" page and collect every
   file NZQA lists: exam papers, resource booklets, exemplars, reports,
   schedules, specifications, PEPs, the standard itself, and ZIPs.
   Later stages prune this down to external papers and schedules only.

Everything written to data/subjects.json comes from an official NZQA page.
No file URLs are guessed.

Run:  ../.venv/bin/python scrape.py
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import atomic

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "subjects.json"

BASE = "https://www2.nzqa.govt.nz"
WWW = "https://www.nzqa.govt.nz"
MASTER = f"{BASE}/ncea/subjects/past-exams-and-exemplars/"
MASTER_PATH = "/ncea/subjects/past-exams-and-exemplars/"

UA = "Mozilla/5.0 (compatible; NCEA-papers-index/1.0)"
SKIP_SLUGS = {"removal-of-older-resources", "past-exams-and-exemplars"}
NAV_LABELS = {
    "go back", "see all subjects", "log in", "search", "home", "menu",
    "print this page", "next", "previous", "back to top", "on this page",
}

DOC_KINDS = [
    ("/exams/", "Exam paper"),
    ("/exemplars/", "Exemplar"),
    ("/reports/", "Assessment report"),
    ("/schedules/", "Assessment schedule"),
    ("/specifications/", "Assessment specification"),
    ("/pep/", "Profile of expected performance"),
    ("/achievements/", "Achievement standard"),
    ("/moderation/", "Moderation material"),
    ("/resources/", "Other resource"),
]


FETCH_ERRORS: list[str] = []


def fetch(url: str, attempts: int = 3) -> str:
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            if i == attempts - 1:
                msg = f"{url}: {exc}"
                FETCH_ERRORS.append(msg)
                print(f"  ! fetch failed: {msg}", file=sys.stderr)
                return ""
            time.sleep(1.5 * (i + 1))
    return ""


def absolute(url: str) -> str:
    # NZQA serves /nqfdocs/ and /bin/ from www, but /assets/ and the site
    # pages from www2. Mixing hosts produces 404s.
    parts = urllib.parse.urlsplit(url)
    if parts.scheme and parts.netloc:
        return url
    host = WWW if parts.path.startswith(("/nqfdocs/", "/bin/")) else BASE
    return urllib.parse.urljoin(host, url)


def text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def clean(label: str) -> str:
    label = re.sub(r"\s*\(external link\)\s*$", "", label, flags=re.I)
    return re.sub(r"\s+", " ", label).strip()


def soup_of(html: str) -> BeautifulSoup:
    s = BeautifulSoup(html, "html.parser")
    return s.find("main") or s


def kind_of_url(url: str) -> str:
    name = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1].lower()
    # Distinct exam-related file roles are encoded in the filename.
    specific = [
        ("-mex-", "Exam paper (Māori)"),
        ("-mre-", "Resource booklet (Māori)"),
        ("-res-", "Resource booklet"),
        ("-exm-", "Exam paper"),
        ("-exp-", "Exemplar"),
        ("-tam-", "Exemplar"),
        ("-report-", "Assessment report"),
        ("-ass-", "Assessment schedule"),
        ("-spc-", "Assessment specification"),
        ("-pep-", "Profile of expected performance"),
    ]
    for fragment, kind in specific:
        if fragment in name:
            return kind
    for fragment, kind in DOC_KINDS:
        if fragment in url:
            return kind
    return "Resource"


def year_of(url: str, label: str = "") -> str:
    m = re.search(r"/(20\d{2})/", url)
    if m:
        return m.group(1)
    m = re.search(r"/(20\d{2})[-_]", url)
    if m:
        return m.group(1)
    name = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
    m = re.search(r"(?:^|[-_])(20\d{2})(?:[-_.]|$)", name)
    if m:
        return m.group(1)
    m = re.search(r"\b(20\d{2})\b", label)
    return m.group(1) if m else ""


def detail_label(url: str) -> str:
    """Human label from a resource filename, e.g. 91170-exm-2025.pdf."""
    name = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
    name = re.sub(r"\.(pdf|zip|docx?)$", "", name, flags=re.I)
    mapping = [
        ("-exm-", "Exam paper"), ("-mex-", "Exam paper (Māori)"),
        ("-res-", "Resource booklet"), ("-mre-", "Resource booklet (Māori)"),
        ("-exp-", "Exemplar"), ("-report-", "Assessment report"),
        ("-ass-", "Assessment schedule"), ("-spc-", "Assessment specification"),
        ("-pep-", "Profile of expected performance"),
    ]
    for fragment, label in mapping:
        if fragment in name:
            grade = re.search(r"-(excellence|merit|achievement)$", name, re.I)
            suffix = " — " + grade.group(1).capitalize() if grade else ""
            return label + suffix
    if re.fullmatch(r"as\d+", name, re.I):
        return "Achievement standard"
    return name


# --------------------------------------------------------------------------
# Stage 1: subjects from the master index
# --------------------------------------------------------------------------
def get_subjects() -> list[dict]:
    print(f"Master index: {MASTER}")
    html = fetch(MASTER)
    if not html:
        return []
    soup = soup_of(html)
    out: list[dict] = []
    seen: set[str] = set()
    for tile in soup.select("a.landing-page__tile-wrapper[href]"):
        href = absolute(tile["href"])
        path = urllib.parse.urlparse(href).path
        if not path.startswith(MASTER_PATH):
            continue
        slug = path.rstrip("/").rsplit("/", 1)[-1]
        if slug in SKIP_SLUGS or slug in seen:
            continue
        seen.add(slug)
        title = tile.select_one(".landing-page__tile-title")
        out.append(
            {
                "slug": slug,
                "name": clean(text(title)) if title else clean(text(tile)),
                "url": f"{MASTER}{slug}/",
            }
        )
    print(f"  {len(out)} subjects")
    return out


# --------------------------------------------------------------------------
# Stage 2: subject landing pages
# --------------------------------------------------------------------------
def parse_landing(html: str, subject: dict) -> dict:
    soup = soup_of(html)
    levels = {str(n): {"links": []} for n in (1, 2, 3)}
    current: int | None = None

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "a"]):
        if tag.name in {"h1", "h2", "h3", "h4"}:
            heading = text(tag).lower()
            # Only a heading that actually starts with "Level N" opens a level.
            m = re.match(r"^(?:ncea\s+)?(?:level|kaupae|taumata)\s*([123])\b", heading)
            if m:
                current = int(m.group(1))
            elif heading.startswith(("see all", "helpful", "i want", "go to")) or "change" in heading or "note" in heading:
                current = None
            continue

        label = clean(text(tag))
        href = tag.get("href", "")
        if not label or not href or label.lower() in NAV_LABELS:
            continue
        if href.startswith(("javascript:", "#", "mailto:")):
            continue
        url = absolute(href)

        if current in (1, 2, 3) and "search.do" in url:
            # Capture every NZQA search link, deriving the kind from the
            # view= parameter rather than relying on heading wording.
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            view = query.get("view", [""])[0].lower()
            if view in {"exams", "reports", "specifications", "all", "files"}:
                levels[str(current)]["links"].append({"label": label, "url": url, "kind": view})

    def dedupe(items: list[dict]) -> list[dict]:
        seen: set[str] = set()
        out = []
        for it in items:
            if it["url"] not in seen:
                seen.add(it["url"])
                out.append(it)
        return out

    for lvl in levels.values():
        lvl["links"] = dedupe(lvl["links"])
    subject["levels"] = levels
    return subject


# --------------------------------------------------------------------------
# Stage 3: search results -> standard rows ; detail pages -> all files
# --------------------------------------------------------------------------
def parse_standards(html: str) -> list[dict]:
    soup = soup_of(html)
    out: list[dict] = []
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        first = clean(text(cells[0]))
        m = re.fullmatch(r"(?:AS\s*)?(\d{4,5})", first, flags=re.I)
        if not m or len(cells) < 4:
            continue
        values = [clean(text(c)) for c in cells]
        out.append(
            {
                "number": m.group(1),
                "subject": values[1] if len(values) > 1 else "",
                "title": values[2] if len(values) > 2 else "",
                "credits": values[3] if len(values) > 3 else "",
                "assessment": values[4] if len(values) > 4 else "",
                "documents": [],
                "detail_url": f"{WWW}/ncea/assessment/view-detailed.do?standardNumber={m.group(1)}",
            }
        )
    return out


def collect_docs(html: str) -> list[dict]:
    """Every NZQA document link on a page, with a label from its table row."""
    soup = soup_of(html)
    out: list[dict] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = absolute(a["href"])
        path = urllib.parse.urlparse(href).path
        is_doc = "/nqfdocs/" in href or "/bin/" in href or (
            "/assets/" in path and DOC_EXT.search(path)
        ) or DOC_EXT.search(path)
        if not is_doc or href in seen:
            continue
        seen.add(href)
        row = a.find_parent("tr")
        label = ""
        if row:
            cells = row.find_all(["td", "th"], recursive=False)
            if cells:
                label = clean(text(cells[0]))
        if not label:
            hint = a.get("title", "")
            if hint:
                label = clean(re.sub(r"^Download\s+", "", hint, flags=re.I))
        if not label or label.startswith("("):
            label = detail_label(href)
        out.append(
            {
                "label": label,
                "type": kind_of_url(href),
                "year": year_of(href, label),
                "url": href,
            }
        )
    return out


def merge_standards(existing: list[dict], new: list[dict]) -> list[dict]:
    by_num = {s["number"]: s for s in existing}
    for s in new:
        if s["number"] in by_num:
            target = by_num[s["number"]]
            for key in ("title", "subject", "credits", "assessment", "detail_url"):
                if not target.get(key) and s.get(key):
                    target[key] = s[key]
            seen_urls = {d["url"] for d in target["documents"]}
            for d in s["documents"]:
                if d["url"] not in seen_urls:
                    seen_urls.add(d["url"])
                    target["documents"].append(d)
        else:
            by_num[s["number"]] = s
            existing.append(s)
    return existing


def specs_url(link_url: str) -> str:
    parts = urllib.parse.urlsplit(link_url)
    query = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
    query["view"] = ["specifications"]
    new_query = urllib.parse.urlencode({k: v[0] for k, v in query.items()})
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, ""))


def harvest_standards(subject: dict) -> None:
    for lvl in ("1", "2", "3"):
        info = subject["levels"][lvl]
        info["standards"] = []

        # Discover the standards from the exam/report search pages and grab
        # the files listed on those pages as well.
        urls: list[str] = []
        for link in info["links"]:
            if link["url"] not in urls:
                urls.append(link["url"])
        for link in info["links"][:1]:
            su = specs_url(link["url"])
            if su not in urls:
                urls.append(su)

        for url in urls:
            html = fetch(url)
            if not html:
                continue
            for std in parse_standards(html):
                merge_standards(info["standards"], [std])
            docs = collect_docs(html)
            if docs:
                # Match documents to standards by any 4-5 digit number in the
                # filename, not just a number-first pattern (years can come first).
                for std in info["standards"]:
                    number = std["number"]
                    existing = {x["url"] for x in std["documents"]}
                    for d in docs:
                        name = urllib.parse.urlparse(d["url"]).path.rsplit("/", 1)[-1]
                        numbers = re.findall(r"\d{4,5}", name)
                        if number in numbers and d["url"] not in existing:
                            std["documents"].append(d)
                            existing.add(d["url"])
            time.sleep(0.12)

        # Each standard's own "View all documents" page is the most complete
        # source: it includes files the search views omit.
        for std in info["standards"]:
            html = fetch(std["detail_url"])
            if not html:
                continue
            for d in collect_docs(html):
                if d["url"] not in {x["url"] for x in std["documents"]}:
                    std["documents"].append(d)
            time.sleep(0.12)

        info["standards"].sort(key=lambda s: (s["number"], s["title"]))


# --------------------------------------------------------------------------
# Stage 3b: enrichment from landing-page files and per-standard pages
# NZQA does not use the search endpoint for every subject. Some pages link
# files under /assets/ directly, and others link a page per standard.
# --------------------------------------------------------------------------
DOC_EXT = re.compile(r"\.(pdf|zip|docx?|xlsx?)$", re.I)
PER_STD = re.compile(r"/past-exams-and-exemplars/[^/]+/(?:as-)?(\d{4,5})/$")


def enrich_subject(subject: dict, landing_html: str) -> None:
    soup = soup_of(landing_html)
    current: int | None = None
    per_std: dict[str, int] = {}  # url -> level

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "a"]):
        if tag.name in {"h1", "h2", "h3", "h4"}:
            heading = text(tag).lower()
            m = re.match(r"^(?:ncea\s+)?(?:level|kaupae|taumata)\s*([123])\b", heading)
            if m:
                current = int(m.group(1))
            elif heading.startswith(("see all", "i want", "go to", "on this page")):
                current = None
            continue

        href = tag.get("href", "")
        if not href:
            continue
        url = absolute(href)

        # Per-standard pages (with or without the "as-" prefix).
        m = PER_STD.search(urllib.parse.urlparse(url).path)
        if m and current in (1, 2, 3):
            per_std[url] = current

    for url, lvl in per_std.items():
        html = fetch(url)
        if not html:
            continue
        m = PER_STD.search(urllib.parse.urlparse(url).path)
        number = m.group(1) if m else ""
        psoup = soup_of(html)
        heading = psoup.find(["h1", "h2"])
        title = clean(text(heading)) if heading else ""
        docs = collect_docs(html)
        if not docs:
            continue
        std = {
            "number": number,
            "subject": subject["name"],
            "title": title,
            "credits": "",
            "assessment": "External" if any(n in title.lower() for n in (" ā-waho", "external")) else "",
            "documents": docs,
            "detail_url": url,
        }
        merge_standards(subject["levels"][str(lvl)]["standards"], [std])
        time.sleep(0.1)


# --------------------------------------------------------------------------
def main() -> int:
    subjects = get_subjects()
    if not subjects:
        return 1

    total = len(subjects)
    for i, subject in enumerate(subjects, 1):
        print(f"[{i:2d}/{total}] {subject['name']}", flush=True)
        page = fetch(subject["url"])
        if not page:
            subject["levels"] = {str(n): {"links": [], "standards": []} for n in (1, 2, 3)}
            continue
        parse_landing(page, subject)
        harvest_standards(subject)
        enrich_subject(subject, page)
        time.sleep(0.12)


    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "source": MASTER,
        "subjects": subjects,
        "fetch_errors": FETCH_ERRORS,
    }
    DATA.parent.mkdir(parents=True, exist_ok=True)
    atomic.write(DATA, json.dumps(payload, indent=1, ensure_ascii=False))

    standards = sum(len(s["levels"][l]["standards"]) for s in subjects for l in ("1", "2", "3"))
    docs = sum(len(std["documents"]) for s in subjects for l in ("1", "2", "3") for std in s["levels"][l]["standards"])
    print(f"\nWrote {DATA}")
    print(f"  subjects          : {len(subjects)}")
    print(f"  external standards: {standards}")
    print(f"  direct documents  : {docs}")
    print(f"  fetch errors      : {len(FETCH_ERRORS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
