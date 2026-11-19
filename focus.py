#!/usr/bin/env python3
"""Narrow the index to EXTERNAL past papers and answer schedules only.

- Keep only standards explicitly assessed externally.
- Keep only English-medium exam papers / resource booklets and answer schedules.
  Drop Māori translations, exemplars, reports, specifications, PEPs, standard
  documents and generic study files.
- Drop any subject with neither a past paper nor an answer schedule.
- Drop Scholarship: its exam material is ZIP-only, not PDF past papers.

Run after fix_and_prune.py, before build.py.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "subjects.json"

KEEP_TYPES = {"Exam paper", "Resource booklet", "Assessment schedule"}
BANNED = re.compile(
    r"(-exp-|-tam-|-sxp-|-sas-|-report-|-spc-|-pep-|exemplar|purongo|expected.learner.response)",
    re.I,
)
MAORI_DOC = re.compile(r"(-mex-|-mre-|maori|māori|hanga rauemi)", re.I)
# Standards that NZQA's keyword search files under the wrong subject.
# Move them to the subject they actually belong to before normalising names.
REASSIGN = {
    ("economics", "Home Economics"): ("home-economics", "Home Economics"),
    ("history", "Art History"): ("art-history", "Art History"),
    ("history", "Visual Arts"): ("visual-arts", "Visual Arts"),
    ("science", "Agricultural & Horticultural Science (AgHort)"):
        ("agricultural-and-horticultural-science", "Agricultural and Horticultural Science"),
    ("science", "Chemistry and Biology (ChemBio)"):
        ("chemistry-and-biology", "Chemistry and Biology"),
    ("science", "Physics, Earth and Space Science (PESS)"):
        ("physics-earth-and-space-science", "Physics, Earth and Space Science"),
}

# Some NZQA search results tag standards with a different subject label
# (including other subjects that matched the keyword). Normalise each subject
# to one canonical name across all three levels.
ALIASES = {
    "agricultural-and-horticultural-science": {
        "Agricultural & Horticultural Science (AgHort)", "Agricultural and Horticultural Science"},
    "chemistry-and-biology": {"Chemistry and Biology (ChemBio)", "Chemistry and Biology"},
    "economics": {"Economics"},
    "history": {"History"},
    "materials-and-processing-technology": {"Materials and Processing Technology (MPT)"},
    "mathematics-and-statistics": {"Mathematics and Statistics", "Mathematics"},
    "nzsl": {"New Zealand Sign Language (NZSL)"},
    "physics-earth-and-space-science": {"Physics, Earth and Space Science (PESS)"},
    "samoan": {"Gagana Sāmoa", "Samoan"},
    "science": {"Science"},
}

MAORI_SLUGS = {
    "hangarau", "hauora", "pangarau", "putaiao",
    "te-reo-maori", "te-reo-rangatira",
    "nga-mahi-a-te-rehia", "tikanga-a-iwi-exemplars",
    "toi-ataata", "toi-puoro", "te-ao-haka",
}


def classify(doc: dict) -> str:
    """Precise type from filename/label; rejected types return 'Excluded'."""
    name = urllib.parse.urlparse(doc["url"]).path.rsplit("/", 1)[-1].lower()
    text = name + " " + doc.get("label", "").lower()
    if BANNED.search(text) or MAORI_DOC.search(text):
        return "Excluded"
    if any(k in text for k in ("mahere", "-ass-", "schedule")):
        return "Assessment schedule"
    if "-res-" in name:
        return "Resource booklet"
    if "-exm-" in name or "exam" in text or "paper" in text or "questions-public" in text:
        return "Exam paper"
    return doc.get("type", "")


def reassign(payload: dict) -> None:
    """Move standards that NZQA's keyword search filed under the wrong subject."""
    by_slug = {s["slug"]: s for s in payload["subjects"]}

    def ensure(slug: str, name: str) -> dict:
        if slug not in by_slug:
            target = {
                "slug": slug, "name": name, "has_past_paper": False,
                "levels": {str(n): {"standards": []} for n in (1, 2, 3)},
            }
            by_slug[slug] = target
            payload["subjects"].append(target)
        return by_slug[slug]

    for (src_slug, tag), (dst_slug, dst_name) in REASSIGN.items():
        src = by_slug.get(src_slug)
        if not src:
            continue
        dst = ensure(dst_slug, dst_name)
        for lvl in ("1", "2", "3"):
            moving = [std for std in src["levels"][lvl]["standards"] if std.get("subject") == tag]
            if not moving:
                continue
            src["levels"][lvl]["standards"] = [
                std for std in src["levels"][lvl]["standards"] if std.get("subject") != tag
            ]
            for std in moving:
                std["subject"] = dst_name
                dst["levels"][lvl]["standards"].append(std)


CALCULUS_STANDARDS = {"91577", "91578", "91579"}
STATISTICS_STANDARDS = {"91584", "91585", "91586"}


def split_l3_maths(payload: dict) -> None:
    """Present Level 3 maths as the two school subjects: Calculus and Statistics."""
    by_slug = {s["slug"]: s for s in payload["subjects"]}
    src = by_slug.get("mathematics-and-statistics")
    if not src:
        return

    def new_subject(slug: str, name: str) -> dict:
        if slug not in by_slug:
            subj = {
                "slug": slug, "name": name, "has_past_paper": False,
                "levels": {str(n): {"standards": []} for n in (1, 2, 3)},
            }
            by_slug[slug] = subj
            payload["subjects"].append(subj)
        return by_slug[slug]

    calculus = new_subject("calculus", "Calculus")
    statistics = new_subject("statistics", "Statistics")
    remaining = []
    for std in src["levels"]["3"]["standards"]:
        if std["number"] in CALCULUS_STANDARDS or std.get("subject") == "Calculus":
            std["subject"] = "Calculus"
            calculus["levels"]["3"]["standards"].append(std)
        elif std["number"] in STATISTICS_STANDARDS or std.get("subject") == "Statistics":
            std["subject"] = "Statistics"
            statistics["levels"]["3"]["standards"].append(std)
        else:
            remaining.append(std)
    src["levels"]["3"]["standards"] = remaining


def dedupe(payload: dict) -> None:
    """Merge duplicate standards by number within each subject/level."""
    for s in payload["subjects"]:
        for lvl in ("1", "2", "3"):
            seen = {}
            out = []
            for std in s["levels"][lvl]["standards"]:
                n = std["number"]
                if n in seen:
                    target = seen[n]
                    urls = {d["url"] for d in target["documents"]}
                    for d in std["documents"]:
                        if d["url"] not in urls:
                            target["documents"].append(d)
                            urls.add(d["url"])
                else:
                    seen[n] = std
                    out.append(std)
            s["levels"][lvl]["standards"] = out


def merge_samoan(payload: dict) -> None:
    """Gagana Sāmoa and Samoan are one subject with two official labels."""
    by_slug = {s["slug"]: s for s in payload["subjects"]}
    src = by_slug.get("gagana-samoa")
    dst = by_slug.get("samoan")
    if not src or not dst:
        return
    for lvl in ("1", "2", "3"):
        dst["levels"][lvl]["standards"].extend(src["levels"][lvl]["standards"])
    payload["subjects"].remove(src)


def main() -> int:
    payload = json.loads(DATA.read_text(encoding="utf-8"))  # malformed data fails loudly
    before = len(payload["subjects"])
    reassign(payload)
    merge_samoan(payload)
    split_l3_maths(payload)
    dedupe(payload)

    for s in payload["subjects"]:
        allowed = ALIASES.get(s["slug"], set()) | {s["name"]}
        has_paper = False
        for lvl in ("1", "2", "3"):
            info = s["levels"][lvl]
            kept_standards = []
            for std in info["standards"]:
                if "external" not in std.get("assessment", "").lower():
                    continue
                if std.get("subject") not in allowed:
                    continue
                std["subject"] = s["name"]
                kept = []
                for d in std["documents"]:
                    d["type"] = classify(d)
                    if d["type"] in KEEP_TYPES:
                        kept.append(d)
                        has_paper = True
                if kept:
                    std["documents"] = kept
                    kept_standards.append(std)
            info["standards"] = kept_standards
        s["has_past_paper"] = has_paper

    dedupe(payload)
    dropped_no_papers = [
        s["slug"] for s in payload["subjects"]
        if not s["has_past_paper"] and s["slug"] not in MAORI_SLUGS
    ]
    payload["subjects"] = [
        s for s in payload["subjects"]
        if s["has_past_paper"] and s["slug"] not in MAORI_SLUGS
    ]

    n_std = sum(len(s["levels"][l]["standards"]) for s in payload["subjects"] for l in ("1", "2", "3"))
    n_docs = sum(len(std["documents"]) for s in payload["subjects"] for l in ("1", "2", "3") for std in s["levels"][l]["standards"])
    payload["focus_report"] = {
        "subjects_before": before,
        "subjects_after": len(payload["subjects"]),
        "standards": n_std,
        "papers_and_schedules": n_docs,
        "dropped_no_papers": dropped_no_papers,
    }
    DATA.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Subjects: {before} -> {len(payload['subjects'])} (external papers only)")
    print(f"standards: {n_std}, papers/schedules: {n_docs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
