#!/usr/bin/env python3
"""Verify the generated PDF-only NCEA index. Exits non-zero on failure."""

from __future__ import annotations

import json
import re
import collections
from html.parser import HTMLParser
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[str] = []
        self.pdf_anchors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrs = dict(attrs)
        href = attrs.get("href")
        if href:
            self.anchors.append(href)
        if str(attrs.get("class", "")).startswith("pdf-") and href:
            self.pdf_anchors.append(href)


def pdf_hrefs(text: str) -> list[str]:
    parser = AnchorParser()
    parser.feed(text)
    return parser.pdf_anchors


class ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            src = dict(attrs).get("src")
            if src:
                self.sources.append(src)


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "subjects.json"
PDF = re.compile(r"\.pdf$", re.I)
JARGON = re.compile(
    r"Examination paper|Assessment schedule|Assessment report|assessment paper|Examination audio or video transcript",
    re.I,
)

errors: list[str] = []


def check(condition: bool, message: str) -> None:
    print(("  ok   " if condition else "  FAIL ") + message)
    if not condition:
        errors.append(message)


def read(path: Path) -> str:
    if not path.exists():
        check(False, f"{path.name} exists")
        return ""
    return path.read_text(encoding="utf-8")


def main() -> int:
    if not DATA.exists():
        check(False, "data/subjects.json exists")
        print("FAILED: missing data")
        return 1
    payload = json.loads(DATA.read_text(encoding="utf-8"))  # malformed data fails loudly
    subjects = payload["subjects"]
    legacy = [k for s in subjects for k in ("internal_only", "source_type") if k in s]
    legacy += [k for s in subjects for l in ("1", "2", "3") for k in ("has_external", "direct_documents")
               if k in s["levels"][l]]
    legacy += [k for s in subjects for l in ("1", "2", "3") for std in s["levels"][l]["standards"]
               for k in ("source_type",) if k in std]
    legacy += [k for s in subjects for l in ("1", "2", "3") for std in s["levels"][l]["standards"]
               for d in std["documents"] for k in ("source_type", "format", "size") if k in d]
    check(not legacy, f"no legacy discarded fields (found: {legacy[:5]})")
    errs = payload.get("fetch_errors") or []
    check(not errs, f"no fetch errors during scrape/enrich ({len(errs)})")

    urls: list[str] = []
    for s in subjects:
        for lvl in ("1", "2", "3"):
            info = s["levels"][lvl]
            for std in info["standards"]:
                urls.extend(d["url"] for d in std["documents"])
    KEEP_TYPES = {"Exam paper", "Resource booklet", "Assessment schedule"}
    banned_doc = re.compile(
        r"(-exp-|-tam-|-report-|-spc-|-pep-|exemplar|purongo|expected.learner.response"
        r"|-mex-|-mre-|maori|māori|-nex-|niuean|niue-|cook.?island|tokelau|samoan|gagana|faka|te.?reo)",
        re.I,
    )
    doc_types = set()
    bad_docs = []
    for s in subjects:
        docs = []
        for lvl in ("1", "2", "3"):
            info = s["levels"][lvl]
            for std in info["standards"]:
                docs.extend(std["documents"])
        doc_types.update(d.get("type", "") for d in docs)
        for d in docs:
            name = urlparse(d["url"]).path.rsplit("/", 1)[-1]
            if banned_doc.search(name + " " + d.get("label", "")):
                bad_docs.append(d["url"])
        recomputed = any(d.get("type") in KEEP_TYPES for d in docs)
        check(recomputed, f"{s['name']} really has papers or schedules")

    print("Scope")
    check(doc_types <= KEEP_TYPES, f"only papers and schedules (found: {sorted(doc_types)})")
    check(not bad_docs, f"no exemplar/report/Māori files (found: {len(bad_docs)})")
    sample_tokens = re.compile(r"(-sxp-|-sas-|-exp-|-tam-)", re.I)
    sample_docs = [d["url"] for s in subjects for l in ("1", "2", "3")
                   for info in [s["levels"][l]] for std in info["standards"] for d in std["documents"]
                   if sample_tokens.search(d["url"])]
    check(not sample_docs, f"no sample/exemplar assessments (found: {len(sample_docs)})")
    non_external = [std["number"] for s in subjects for l in ("1", "2", "3")
                    for std in s["levels"][l]["standards"]
                    if "external" not in std.get("assessment", "").lower()]
    check(not non_external, f"all standards are external (bad: {non_external[:8]})")
    core = {"English", "Mathematics and Statistics", "Science", "Physics", "Chemistry", "Biology",
            "History", "Geography", "Economics", "Accounting", "Business Studies",
            "Digital Technologies", "Physical Education", "Music", "Art History",
            "Materials and Processing Technology", "New Zealand Sign Language",
            "Physics, Earth and Space Science", "Samoan", "Home Economics",
            "Agricultural and Horticultural Science", "Chemistry and Biology",
            "Calculus", "Statistics", "Design and Visual Communication",
            "Technology", "Visual Arts", "Literacy and Numeracy",
            "Cook Islands Māori", "Gagana Tokelau", "Lea Faka-Tonga",
            "Te Reo Māori Kūki ‘Āirani", "Vagahau Niue"}
    names = {s["name"].lower() for s in subjects}
    missing_core = sorted(c for c in core if c.lower() not in names)
    check(not missing_core, f"core subjects present (missing: {missing_core})")
    check(len(subjects) >= 30, f"{len(subjects)} subjects (>= 30, broad coverage)")
    check("scholarship" not in payload, "no Scholarship ZIP-only section")
    check("Scholarship" not in read(ROOT / "index.html"),
          "no Scholarship option in picker")
    mismatched = []
    for s in subjects:
        names = {std.get("subject", "") for l in ("1", "2", "3") for std in s["levels"][l]["standards"]}
        if names and (len(names) != 1 or next(iter(names)) != s["name"]):
            mismatched.append(s["name"])
    check(not mismatched, f"one consistent subject name across all levels (bad: {mismatched})")
    dup_names = [name for name, count in collections.Counter(s["name"] for s in subjects).items() if count > 1]
    check(not dup_names, f"no duplicate subject names (bad: {dup_names})")
    dup_slugs = [slug for slug, count in collections.Counter(s["slug"] for s in subjects).items() if count > 1]
    check(not dup_slugs, f"no duplicate subject slugs (bad: {dup_slugs})")
    dup_std = [(s["slug"], l, n) for s in subjects for l in ("1", "2", "3")
               for n, count in collections.Counter(std["number"] for std in s["levels"][l]["standards"]).items()
               if count > 1]
    check(not dup_std, f"no duplicate standards (bad: {dup_std[:6]})")
    all_numbers = [(std["number"], s["slug"], l) for s in subjects for l in ("1", "2", "3")
                   for std in s["levels"][l]["standards"]]
    seen_numbers = {}
    collisions = []
    for number, slug, lvl in all_numbers:
        key = (number,)
        if key in seen_numbers and seen_numbers[key] != (slug, lvl):
            collisions.append(number)
        seen_numbers[key] = (slug, lvl)
    check(not collisions, f"jump numbers globally unique (collisions: {collisions[:6]})")
    placeholders = [std["number"] for s in subjects for l in ("1", "2", "3")
                    for std in s["levels"][l]["standards"]
                    if std.get("title") in ("External assessment schedules", "External assessment")
                    or not std.get("credits")]
    check(not placeholders, f"every standard has a real title and credits (bad: {placeholders[:6]})")
    by_slug = {s["slug"]: s for s in subjects}
    split_maths = by_slug.get("mathematics-and-statistics")
    calc = by_slug.get("calculus")
    stats = by_slug.get("statistics")
    check(bool(split_maths and calc and stats), "L3 maths split subjects exist")
    if split_maths and calc and stats:
        calc_nums = {std["number"] for std in calc["levels"]["3"]["standards"]}
        stat_nums = {std["number"] for std in stats["levels"]["3"]["standards"]}
        check(calc_nums == {"91577", "91578", "91579"}, f"Calculus L3 standards {sorted(calc_nums)}")
        check(stat_nums == {"91584", "91585", "91586"}, f"Statistics L3 standards {sorted(stat_nums)}")
        check(not split_maths["levels"]["3"]["standards"], "Maths L3 emptied by split")
        check(bool(split_maths["levels"]["1"]["standards"] and split_maths["levels"]["2"]["standards"]),
              "Maths L1/L2 retained")

    n_std = sum(len(s["levels"][l]["standards"]) for s in subjects for l in ("1", "2", "3"))
    rep = payload.get("focus_report", {})
    check(rep.get("papers_and_schedules") == len(urls), "focus_report PDF count matches data")
    check(rep.get("standards") == n_std, "focus_report standard count matches data")
    check(rep.get("subjects_after") == len(subjects), "focus_report subject count matches data")
    link_report_path = ROOT / "data" / "link_report.json"
    if link_report_path.exists():
        dead_urls = json.loads(link_report_path.read_text(encoding="utf-8")).get("dead", [])
        check(not [u for u in dead_urls if u in urls],
              f"no dead URL shipped in the index (dead recorded: {len(dead_urls)})")

    baseline_path = ROOT / "data" / "baseline.json"
    check(baseline_path.exists(), "baseline.json present for drift detection")
    if baseline_path.exists():
        base = json.loads(baseline_path.read_text(encoding="utf-8"))
        cur_s = {s["slug"] for s in subjects}
        base_s = set(base["subjects"])
        check(not base_s - cur_s, f"baseline subjects still present (missing: {sorted(base_s - cur_s)})")
        cur_std = {(s["slug"], l, std["number"]) for s in subjects for l in ("1", "2", "3")
                   for std in s["levels"][l]["standards"]}
        base_std = {tuple(x) for x in base["standards"]}
        check(not base_std - cur_std, f"baseline standards still present (missing: {sorted(base_std - cur_std)[:8]})")
        if cur_std - base_std:
            print(f"  note  {len(cur_std - base_std)} new standards not in baseline: {sorted(cur_std - base_std)[:8]}")

    print("PDF-only data")
    check(len(urls) > 1000, f"{len(urls):,} direct PDF links")
    check(all(PDF.search(u) for u in urls), "every link ends in .pdf")
    check(all(u.startswith("https://") for u in urls), "every link is https")
    check(all(urlparse(u).netloc in {"www.nzqa.govt.nz", "www2.nzqa.govt.nz"} for u in urls), "every link is on NZQA")
    check(all("/nqfdocs/" not in u or urlparse(u).netloc == "www.nzqa.govt.nz" for u in urls), "nqfdocs uses www host")
    check(all("/assets/" not in u or urlparse(u).netloc == "www2.nzqa.govt.nz" for u in urls), "assets uses www2 host")

    # No HTML-page or ZIP/DOC links may remain in the data.
    banned = re.compile(r"\.(zip|docx?|xlsx?|html?)$", re.I)
    check(not [u for u in urls if banned.search(u)], "no ZIP/DOC/HTML links")
    check(not any(k in payload for k in ("digital_exams", "digital_exams_url")), "no login-page / digital links")
    check(all("detail_url" not in std and "zip_url" not in std
              for s in subjects for l in ("1", "2", "3") for std in s["levels"][l]["standards"]),
          "no detail-page or ZIP links on standards")

    print(f"\nCoverage")
    levels = {l: sum(len(s["levels"][l]["standards"]) for s in subjects) for l in ("1", "2", "3")}
    print(f"       standards: {levels}")
    check(all(v > 0 for v in levels.values()), "all three levels present")
    check(n_std >= 100, f"{n_std} standards")
    years = Counter(d["year"] for s in subjects for l in ("1", "2", "3")
                    for std in s["levels"][l]["standards"] for d in std["documents"])
    print(f"       years: {dict(sorted(years.items(), reverse=True))}")
    check(all(years.get(str(y), 0) > 0 for y in range(2021, 2027)),
          f"all years 2021–2026 present: {dict(sorted(years.items(), reverse=True))}")

    report = payload.get("prune_report", {})
    print(f"\nLink check: {report.get('urls_live')}/{report.get('urls_checked')} live at prune time")
    link_report_path = ROOT / "data" / "link_report.json"
    if link_report_path.exists():
        status = json.loads(link_report_path.read_text(encoding="utf-8")).get("statuses", {})
        not_live = [u for u in set(urls) if status.get(u) not in (200, 206)]
        check(not not_live, f"every included URL has a live 200/206 status ({len(not_live)} missing)")
    else:
        check(False, "link_report.json exists")

    print("\nBuild outputs")
    for name in ("index.html", "all.html", "data.js", "app.js", "styles.css",
                 "verify_ui.js", "friendly.json", "package.json",
                 "privacy.html", "accessibility.html", "disclaimer.html"):
        check((ROOT / name).exists(), f"{name} exists")
    check(len(list((ROOT / "subjects").glob("*/index.html"))) > 20, "subject pages exist")
    ui_js = read(ROOT / "verify_ui.js")
    ui_calls = len(re.findall(r"^\s*check\(", ui_js, re.M))
    check(ui_calls == 23, f"UI smoke suite has exactly 23 checks (found {ui_calls})")
    rebuild = read(ROOT / "rebuild_all.sh")
    active = "\n".join(line.split("#", 1)[0] for line in rebuild.splitlines())
    check(bool(re.search(r"^\s*\.\./\.venv/bin/python test_links\.py\s*$", active, re.M))
          and bool(re.search(r"^\s*REQUIRE_UI=1 node verify_ui\.js\s*$", active, re.M)),
          "pipeline invokes both live check commands")
    check("SKIP_LINK_SAMPLE" in active and "SKIP_UI" in active
          and "jsdom/package.json" in active
          and "require('./package.json')" in active,
          "pipeline keeps both opt-outs and reads the pinned UI version")
    try:
        subprocess_run = __import__("subprocess").run(
            ["sh", "-n", str(ROOT / "rebuild_all.sh")], capture_output=True, timeout=5
        )
        check(subprocess_run.returncode == 0, "rebuild_all.sh has valid shell syntax")
    except Exception as exc:  # noqa: BLE001
        check(False, f"rebuild_all.sh syntax check failed ({exc})")
    if (ROOT / "data.js").exists():
        js = read(ROOT / "data.js")
        check(js.startswith("window.NCEA_DATA = "), "data.js assigns window.NCEA_DATA")
        check(len(js.encode("utf-8")) > 100000, f"data.js populated ({len(js.encode('utf-8')):,} bytes)")
        try:
            embedded = json.loads(js[len("window.NCEA_DATA = "):].rstrip().rstrip(";"))
            embedded_urls = sorted(
                [d["url"] for s in embedded["subjects"] for l in ("1", "2", "3")
                 for std in s["levels"][l]["standards"] for d in std["documents"]]
            )
            check(len(embedded["subjects"]) == len(subjects) and embedded_urls == sorted(urls),
                  f"data.js matches all {len(urls):,} source PDF URLs ({len(js.encode('utf-8')):,} bytes)")
            check(embedded.get("generated") == payload.get("generated", "")[:10],
                  "data.js generated date matches data")
            shared = json.loads((ROOT / "friendly.json").read_text(encoding="utf-8"))["pairs"]
            check(embedded.get("friendly") == shared, "data.js label rules match friendly.json")
        except Exception as exc:  # noqa: BLE001
            check(False, f"data.js parses ({exc})")
    idx = read(ROOT / "index.html")
    check('id="level"' in idx and 'id="subject"' in idx and 'id="external"' in idx, "3-step picker present")
    check('aria-live="polite"' in idx, "status changes announced to screen readers")
    check('<main id="main" tabindex="-1">' in idx, "focusable main landmark present")
    check('class="skip" href="#main"' in idx, "skip link present on picker")
    check('name="referrer" content="no-referrer"' in idx, "no-referrer policy present on picker")
    check('name="description"' in idx, "index meta description present")
    check('id="external-label"' not in idx, "no dead attribute")
    parser = ScriptParser()
    parser.feed(idx)
    scripts = parser.sources
    check("data.js" in scripts and "app.js" in scripts
          and scripts.index("data.js") < scripts.index("app.js"),
          f"data.js loads before app.js (scripts: {scripts})")
    if (ROOT / "all.html").exists():
        page = read(ROOT / "all.html")
        check(("List last checked " + payload.get("generated", "")[:10]) in page,
              "all.html last-checked date matches data")
        check(page.count("<table>") > 100, f"all.html has {page.count('<table>')} PDF tables")
        check('name="description"' in page, "all.html meta description present")
        anchor_text = " ".join(re.findall(r">([^<>]+)</a>", page))
        jargon = len(JARGON.findall(anchor_text))
        check(jargon == 0, f"generated link text uses student-friendly wording (jargon: {jargon})")
        check(len(pdf_hrefs(page)) == len(urls),
              f"all.html contains all {len(urls):,} PDF anchors (found {len(pdf_hrefs(page))})")
        check(sorted(pdf_hrefs(page)) == sorted(urls), "all.html PDF hrefs match data URLs")
        note = "No question paper is listed"
        blocks = [b for b in re.split(r"(?=<h4>)", page) if "<h4>" in b]
        note_blocks = [b for b in blocks if note in b]
        check(len(note_blocks) == page.count(note),
              f"all.html schedule-only notes are attached to standards ({len(note_blocks)} notes)")
    app = read(ROOT / "app.js")
    check('id="picker"' in idx and "Back to the picker" in app, "back-to-picker control present")
    check("nqfdocs" not in app and "search.do" not in app, "UI contains no page/ZIP links")
    subj_pages = list((ROOT / "subjects").glob("*/index.html"))
    missing_viewport = [p.name for p in subj_pages if 'name="viewport"' not in read(p)]
    check(not missing_viewport, f"all subject pages have viewport meta (missing: {missing_viewport[:3]})")
    check({p.parent.name for p in subj_pages} == {s["slug"] for s in subjects},
          f"subject pages match data slugs ({len(subj_pages)} pages)")
    per_page_bad = []
    for p in subj_pages:
        slug = p.parent.name
        text = read(p)
        expected = sorted(
            d["url"] for s in subjects if s["slug"] == slug
            for l in ("1", "2", "3") for std in s["levels"][l]["standards"]
            for d in std["documents"]
        )
        if sorted(pdf_hrefs(text)) != expected:
            per_page_bad.append(slug)
        if JARGON.findall(" ".join(re.findall(r">([^<>]+)</a>", text))):
            per_page_bad.append(slug + ":jargon")
    check(not per_page_bad, f"each subject page has its own PDF URLs and friendly labels (bad: {per_page_bad[:5]})")

    # Generated pages: every resource link must be a direct NZQA PDF.
    def bad_hrefs(text: str, page_path: Path) -> list[str]:
        parser = AnchorParser()
        parser.feed(text)
        bad = []
        for href in parser.anchors:
            if href.startswith(("index.html", "all.html", "privacy.html", "accessibility.html",
                                "disclaimer.html", "subjects/", "../..", "styles.css", "#")):
                continue
            if href == "https://www2.nzqa.govt.nz/about-this-site/copyright/" and page_path.name == "disclaimer.html":
                continue
            if href == "https://github.com/Doodlise/ncea-papers/issues":
                continue
            if re.search(r"\.pdf$", href, re.I) and href.startswith("https://www.nzqa.govt.nz/"):
                continue
            if re.search(r"\.pdf$", href, re.I) and href.startswith("https://www2.nzqa.govt.nz/"):
                continue
            bad.append(href)
        return bad

    broken_anchors = []
    stale_dates = []
    expected_date = "List last checked " + payload.get("generated", "")[:10]
    all_pages = ([ROOT / "index.html", ROOT / "all.html", ROOT / "privacy.html",
                  ROOT / "accessibility.html", ROOT / "disclaimer.html"]
                 + list((ROOT / "subjects").glob("*/index.html")))
    for page_path in all_pages:
        if not page_path.exists():
            continue  # existence already reported by the Build outputs check
        text = read(page_path)
        bad = bad_hrefs(text, page_path)
        check(not bad, f"{page_path.relative_to(ROOT)} has no non-PDF links" + (f" (bad: {bad[:2]})" if bad else ""))
        if page_path != ROOT / "index.html" and expected_date not in text:
            stale_dates.append(str(page_path.relative_to(ROOT)))
        if ('class="skip" href="#main"' not in text
                or '<main id="main" tabindex="-1">' not in text
                or 'name="referrer" content="no-referrer"' not in text
                or "site-footer" not in text
                or "Not operated by, affiliated with, or endorsed by" not in text):
            broken_anchors.append(str(page_path.relative_to(ROOT)) + ":compliance-notice")
        ids = set(re.findall(r'id="([^"]+)"', text))
        for anchor in re.findall(r'href="#([^"]+)"', text):
            if not anchor:
                continue
            if anchor not in ids:
                broken_anchors.append(f"{page_path.relative_to(ROOT)}#{anchor}")
            elif anchor != "main" and f'id="{anchor}" tabindex="-1"' not in text:
                broken_anchors.append(f"{page_path.relative_to(ROOT)}#{anchor}:not-focusable")
    check(not broken_anchors, f"all in-page links resolve (broken: {broken_anchors[:5]})")
    check(not stale_dates, f"all generated pages carry the current date (stale: {stale_dates[:5]})")

    if (ROOT / "data.js").exists():
        urls_in_js = re.findall(r'"url":"([^"]+)"', read(ROOT / "data.js"))
        def good_url(u: str) -> bool:
            p = urlparse(u)
            return (p.scheme == "https" and p.netloc in {"www.nzqa.govt.nz", "www2.nzqa.govt.nz"}
                    and p.path.lower().endswith(".pdf"))
        bad_js = [u for u in urls_in_js if not good_url(u)]
        check(not bad_js, f"all {len(urls_in_js):,} data.js URLs are direct NZQA PDFs (bad: {bad_js[:2]})")

    print()
    if errors:
        print(f"FAILED: {len(errors)} check(s)")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
