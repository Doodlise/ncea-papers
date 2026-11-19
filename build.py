#!/usr/bin/env python3
"""Render data/subjects.json into the site. Only direct PDF links are emitted."""

from __future__ import annotations

import html
import json
import os
import re
from collections import Counter
import shutil
import urllib.parse
from pathlib import Path

import atomic

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "subjects.json"


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


CONTACT_URL = "https://github.com/Doodlise/ncea-papers/issues"
SKIP_LINK = '<a class="skip" href="#main">Skip to main content</a>'


def site_footer(prefix: str, generated: str) -> str:
    links = (
        f'<a href="{prefix}index.html">Home</a> · '
        f'<a href="{prefix}all.html">All PDFs</a> · '
        f'<a href="{prefix}privacy.html">Privacy</a> · '
        f'<a href="{prefix}accessibility.html">Accessibility</a> · '
        f'<a href="{prefix}disclaimer.html">Disclaimer &amp; terms</a> · '
        f'<a href="{CONTACT_URL}" target="_blank" rel="noopener noreferrer">Report a broken link</a>'
    )
    return (
        '<footer class="site-footer">'
        '<p><strong>Unofficial, independent study index.</strong> Not operated by, affiliated with, '
        'or endorsed by the New Zealand Qualifications Authority (NZQA). All PDFs are hosted by NZQA '
        'and linked for private study and reference only. Exam papers may contain third-party '
        'copyright. Copyright in NZQA material belongs to NZQA.</p>'
        f'<p><span class="checked">List last checked {esc(generated)}.</span> {links}</p>'
        '</footer>'
    )


def page_shell(title: str, description: str, body: str, prefix: str, generated: str) -> str:
    return (
        '<!DOCTYPE html><html lang="en-NZ"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="referrer" content="no-referrer">'
        '<link rel="icon" href="data:,">'
        + (f'<meta name="description" content="{esc(description)}">' if description else "")
        + f'<title>{esc(title)}</title>'
        f'<link rel="stylesheet" href="{prefix}styles.css"></head><body>'
        + SKIP_LINK + '<main id="main" tabindex="-1">' + body + "</main>"
        + site_footer(prefix, generated) + "</body></html>\n"
    )


write_atomic = atomic.write


ALLOWED_HOSTS = {"www.nzqa.govt.nz", "www2.nzqa.govt.nz"}


def is_pdf_url(url: str) -> bool:
    p = urllib.parse.urlsplit(url)
    return p.scheme == "https" and p.netloc in ALLOWED_HOSTS and p.path.lower().endswith(".pdf")


def a_pdf(doc: dict, label: str | None = None) -> str:
    url = doc["url"]
    if not is_pdf_url(url):
        raise ValueError(f"non-PDF link reached renderer: {url}")
    text = label if label is not None else friendly(doc.get("label") or "PDF")
    cls = "pdf-answers" if re.search(r"answer|schedul|marking", text, re.I) else "pdf-paper"
    return f'<a class="{cls}" href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(text)}</a>'


FRIENDLY = [tuple(pair) for pair in json.loads(
    (ROOT / "friendly.json").read_text(encoding="utf-8")
)["pairs"]]


def validate_friendly_patterns() -> None:
    """Fail the build if a label rule is valid in Python but not in JS."""
    import subprocess
    for old, _ in FRIENDLY:
        try:
            result = subprocess.run(
                ["node", "-e", "new RegExp(" + json.dumps(old) + ", 'gi')"],
                capture_output=True, timeout=5,
            )
        except FileNotFoundError:
            return  # Node not installed; UI smoke test will catch drift instead.
        if result.returncode:
            raise ValueError(f"friendly.json pattern is invalid in JavaScript: {old!r}")


validate_friendly_patterns()


def friendly(text) -> str:
    out = str(text or "")
    for old, new in FRIENDLY:
        out = re.sub(old, new, out, flags=re.I)
    if not re.search(r"\s", out) and re.search(r"[-_]", out):
        out = re.sub(r"[_-]+", " ", out)
        out = re.sub(r"\.(pdf|zip)$", "", out, flags=re.I)
        out = re.sub(r"\bassessment schedule\b", "schedule", out, flags=re.I)
        out = re.sub(r"\bmarking schedule\b", "schedule", out, flags=re.I)
        out = re.sub(r"\bassessment paper\b", "paper", out, flags=re.I)
        if re.search(r"schedule|marking", out, re.I):
            out = "Answer schedule — " + re.sub(r"^\s*(schedule|marking)\s+", "", out, flags=re.I)
        elif re.search(r"paper|exam", out, re.I):
            out = "Exam paper — " + out
    return out


GENERIC = {"Exam paper", "Answer schedule", "paper", "PDF"}


def url_qualifier(url: str) -> str:
    name = re.split(r"[?#]", str(url or ""), maxsplit=1)[0].rsplit("/", 1)[-1]
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    code = re.match(r"^(\d{4,5}[A-Za-z]?[-_]\d+)(?:[-_]|$)", name)
    if code:
        return re.sub(r"_", "-", code.group(1))
    week = re.search(r"\bweek[-_ ]?(\d+)\b", name, re.I)
    if week:
        return "week " + week.group(1)
    part = re.search(r"[-_](vtr|atr|part|pt)[-_]?(\d+)", name, re.I)
    if part:
        return ("video " if part.group(1).lower() == "vtr" else "part ") + part.group(2)
    return ""


def pdf_rows(docs: list[dict]) -> str:
    ordered = sorted(docs, key=lambda x: (x.get("year", ""), x.get("label", "")), reverse=True)
    labels = [friendly(d.get("label") or "PDF") for d in ordered]
    counts = Counter(labels)
    seen: Counter = Counter()
    rows = []
    for d, label in zip(ordered, labels):
        total = counts[label]
        if total > 1 and (label in GENERIC or label.lower().startswith("audio or video transcript")):
            quals = [
                url_qualifier(x["url"]) for x in ordered
                if friendly(x.get("label") or "PDF") == label
            ]
            if all(quals) and len(set(quals)) == len(quals):
                label = f"{label} — {url_qualifier(d['url'])}"
                rows.append("<tr><td>" + a_pdf(d, label) + "</td></tr>")
                continue
        if total > 1:
            seen[label] += 1
            label = f"{label} ({seen[label]} of {total})"
        rows.append("<tr><td>" + a_pdf(d, label) + "</td></tr>")
    return "".join(rows)


def table(docs: list[dict], heading: str = "h4") -> str:
    """One bordered box per year, newest first."""
    if not docs:
        return ""
    by_year: dict[str, list[dict]] = {}
    for d in docs:
        by_year.setdefault(d.get("year") or "Other", []).append(d)
    parts = []
    years = sorted((y for y in by_year if y != "Other"), reverse=True)
    if "Other" in by_year:
        years.append("Other")
    for year in years:
        parts.append('<section class="year-box">')
        label = esc(year) if year != "Other" else "Other papers and schedules (no year listed)"
        label += f" ({len(by_year[year])})"
        parts.append(f"<{heading}>{label}</{heading}>")
        parts.append(
            '<table><thead><tr><th scope="col">PDF file</th></tr></thead>'
            "<tbody>" + pdf_rows(by_year[year]) + "</tbody></table>"
        )
        parts.append("</section>")
    return "".join(parts)


def all_docs(payload: dict):
    for s in payload["subjects"]:
        for lvl in ("1", "2", "3"):
            info = s["levels"][lvl]
            for std in info["standards"]:
                yield from std["documents"]

def main() -> int:
    payload = json.loads(DATA.read_text(encoding="utf-8"))  # malformed data fails loudly
    if "focus_report" not in payload or "scholarship" in payload or "digital_exams" in payload:
        raise ValueError("data has not been through fix_and_prune.py + focus.py; refusing to build")
    subjects = payload["subjects"]

    # Validate everything BEFORE writing any output, so a bad URL can never
    # be left on disk in data.js.
    for doc in all_docs(payload):
        if not is_pdf_url(doc["url"]):
            raise ValueError(f"non-PDF link reached renderer: {doc['url']}")
    for s in subjects:
        if not re.fullmatch(r"[a-z0-9-]+", s["slug"]):
            raise ValueError(f"bad subject slug: {s['slug']}")

    # data.js — only the fields app.js actually reads. Keep the full payload
    # for the generated HTML pages and verification; trim this browser artifact.
    js_payload = {
        "generated": payload.get("generated", "")[:10],
        "friendly": [list(pair) for pair in FRIENDLY],
        "subjects": [
            {
                "slug": s["slug"],
                "name": s["name"],
                "levels": {
                    lvl: {
                        "standards": [
                            {
                                "number": std["number"],
                                "title": std.get("title", ""),
                                "documents": [
                                    {"label": d.get("label", ""), "year": d.get("year", ""), "url": d["url"]}
                                    for d in std["documents"]
                                ],
                            }
                            for std in s["levels"][lvl]["standards"]
                        ]
                    }
                    for lvl in ("1", "2", "3")
                },
            }
            for s in subjects
        ]
    }
    js = "window.NCEA_DATA = " + json.dumps(js_payload, ensure_ascii=False, separators=(",", ":")) + ";\n"

    # all.html — every PDF, grouped by level, subject, standard, year.
    generated = payload.get("generated", "")[:10]
    body = [
        '<h1 id="top" tabindex="-1">NCEA Past Papers — all PDFs</h1>',
        "<p>Past papers and answer schedules. Every link opens a direct NZQA PDF in a new tab. Coverage is mainly 2021–2026; answer schedules for the newest year often come out later.</p>",
        '<p>Works offline — only the PDF links need internet.</p>',
        '<nav><a href="#level-1">Level 1</a> | <a href="#level-2">Level 2</a> | <a href="#level-3">Level 3</a> | <a href="#top">Back to top</a></nav>',
        '<p class="back-link"><a href="index.html">Back to the picker</a></p>',
    ]
    for lvl in ("1", "2", "3"):
        body.append(f'<h2 id="level-{lvl}" tabindex="-1">Level {lvl}</h2>')
        body.append('<p class="back-link"><a href="#top">Back to top</a></p>')
        at_level = [s for s in subjects if s["levels"][lvl]["standards"]]
        for s in sorted(at_level, key=lambda x: x["name"].lower()):
            body.append(f'<h3><a href="subjects/{esc(s["slug"])}/index.html">{esc(s["name"])}</a></h3>')
            info = s["levels"][lvl]
            for std in info["standards"]:
                body.append(f"<h4>{esc(std['number'])} — {esc(std.get('title', ''))}</h4>")
                if all(re.search(r"answer|schedul|marking", friendly(d.get("label") or "PDF"), re.I)
                   for d in std["documents"]):
                    body.append("<p>No question paper is listed — only answer booklets and schedules.</p>")
                body.append(table(std["documents"], heading="h5"))
    shell = page_shell(
        "NCEA Past Papers — all PDFs",
        "All NCEA past exam papers and answer schedules — direct NZQA PDFs.",
        "".join(body), "", generated,
    )

    # Public-facing notices. Kept as plain HTML, generated so every page agrees.
    legal_pages = {
        "privacy.html": (
            "Privacy",
            "<h1>Privacy</h1>"
            "<p>This site collects no personal information. There are no cookies, analytics, "
            "advertising, forms or account logins, and nothing you type here is sent to us.</p>"
            "<p>Your browser remembers your last selected standard in local storage on your own "
            "device (<code>ncea-papers-last</code>) so it can reopen where you left off. You can "
            "clear it at any time through your browser's site-data settings.</p>"
            "<p>When you follow a PDF link you leave this site and go to NZQA, whose privacy "
            "statement then applies. The hosting provider logs IP addresses for security as "
            "described in its privacy statement.</p>"
            f"<p>Questions: <a href=\"{CONTACT_URL}\" target=\"_blank\" rel=\"noopener noreferrer\">report an issue</a>.</p>",
        ),
        "accessibility.html": (
            "Accessibility",
            "<h1>Accessibility</h1>"
            "<p>This site aims to meet <strong>WCAG 2.2 Level AA</strong>. It uses plain HTML, "
            "high-contrast text, visible keyboard focus, semantic headings and landmarks, and "
            "works at mobile widths and without JavaScript (use the plain list).</p>"
            "<p>Assessed against WCAG 2.2 AA in November 2026, including automated checks and "
            "manual keyboard and screen-reader-oriented review. Known limitations: very long "
            "NZQA document titles may need horizontal scrolling on a 320px-wide screen, and "
            "some past papers are scanned PDFs that may not be fully readable by screen readers.</p>"
            f"<p>Found a barrier? <a href=\"{CONTACT_URL}\" target=\"_blank\" rel=\"noopener noreferrer\">tell us</a>.</p>",
        ),
        "disclaimer.html": (
            "Disclaimer and terms",
            "<h1>Disclaimer and terms</h1>"
            "<p>This is an unofficial, independent study index. It is not operated by, affiliated "
            "with, or endorsed by the New Zealand Qualifications Authority (NZQA).</p>"
            "<p>All PDFs are hosted by NZQA and are linked here for private study and reference "
            "only. Exam papers may contain third-party copyright. Copyright in NZQA material "
            "belongs to NZQA. We do not copy or host any exam material.</p>"
            "<p>The site is free, non-commercial and provided as-is. Links may change or disappear "
            "as NZQA updates its website; we are not responsible for content on NZQA's site. "
            "Please check the original paper for the current version.</p>"
            '<p>NZQA\'s own copyright information: <a href="https://www2.nzqa.govt.nz/about-this-site/copyright/" '
            'target="_blank" rel="noopener noreferrer">NZQA copyright</a>.</p>',
        ),
    }
    for filename, (title, body) in legal_pages.items():
        write_atomic(ROOT / filename, page_shell(title, "", body, "", generated))

    # Render every subject page BEFORE touching the existing subject tree, so
    # a rendering error cannot leave a partially rebuilt directory.
    subject_pages = []
    for s in subjects:
        parts = [
            f'<h1 id="top" tabindex="-1">{esc(s["name"])}</h1>',
            f"<p class=\"intro\">Past papers and answer schedules for {esc(s['name'])}. "
            "Every link opens a direct NZQA PDF in a new tab. Coverage is mainly 2021–2026; "
            "answer schedules for the newest year often come out later.</p>",
            '<p>Works offline — only the PDF links need internet.</p>',
            '<nav>'
            + " | ".join(
                [f'<a href="#level-{lvl}">Level {lvl}</a>' for lvl in ("1", "2", "3")
                 if s["levels"][lvl]["standards"]]
                + ['<a href="#top">Back to top</a>']
            ) + '</nav>',
            '<p class="back-link"><a href="../../all.html">All PDFs</a> | <a href="../../index.html">Back to the picker</a></p>',
        ]
        for lvl in ("1", "2", "3"):
            info = s["levels"][lvl]
            if not info["standards"]:
                continue
            parts.append(f'<h2 id="level-{lvl}" tabindex="-1">{esc("Level " + lvl)}</h2>')
            for std in info["standards"]:
                parts.append(f"<h3>{esc(std['number'])} — {esc(std.get('title', ''))}</h3>")
                if all(re.search(r"answer|schedul|marking", friendly(d.get("label") or "PDF"), re.I)
                   for d in std["documents"]):
                    parts.append("<p>No question paper is listed — only answer booklets and schedules.</p>")
                parts.append(table(std["documents"]))
        parts.append('<p class="back-link"><a href="../../index.html">Back to the picker</a> | '
                     '<a href="../../all.html">All PDFs</a></p>')
        page = page_shell(
            s["name"] + " — NCEA PDFs",
            s["name"] + " NCEA past papers and answer schedules — direct NZQA PDFs.",
            "".join(parts), "../../", generated,
        )
        subject_pages.append((s["slug"], page))

    # Only now replace the subject tree.
    subjects_dir = ROOT / "subjects"
    tmp_dir = ROOT / "subjects.tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir()
    for slug, page in subject_pages:
        (tmp_dir / slug).mkdir()
        write_atomic(tmp_dir / slug / "index.html", page)
    backup = ROOT / "subjects.old"
    if backup.exists():
        shutil.rmtree(backup)
    if subjects_dir.exists():
        os.replace(subjects_dir, backup)
    os.replace(tmp_dir, subjects_dir)
    # All rendering succeeded; only now replace the top-level artifacts.
    write_atomic(ROOT / "data.js", js)
    write_atomic(ROOT / "all.html", shell)
    if backup.exists():
        shutil.rmtree(backup)

    n_pdf = sum(
        len(std["documents"])
        for s in subjects
        for lvl in ("1", "2", "3")
        for std in s["levels"][lvl]["standards"]
    )
    print(f"data.js      : {len(js.encode('utf-8')):,} bytes")
    print(f"all.html     : {len(shell.encode('utf-8')):,} bytes")
    print(f"subject pages: {len(subjects)}")
    print(f"PDF links    : {n_pdf:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
