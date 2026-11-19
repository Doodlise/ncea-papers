# NCEA Past Papers — PDF-only index

A deliberately plain static website. Pick **Level → Subject → Standard** and
get **direct NZQA PDF links** for that standard: past exam papers and answer
schedules only, grouped into a box per year (newest first). Only external
assessments and subjects that actually have past papers or answer schedules are included. Level 3
Mathematics is split into the two school subjects **Calculus** and **Statistics**
(Levels 1–2 remain "Mathematics and Statistics"). Māori-medium subjects and Māori translations of English-medium subjects,
internal material, exemplars, reports and Scholarship ZIPs are excluded.
Pacific language subjects and Literacy & Numeracy are included.

**Every link on this site opens a PDF.** No HTML landing pages, no ZIP bundles,
no DOC files, no login pages. Every included PDF was checked against NZQA and
dead links were removed.

## Files

| File | Purpose |
| --- | --- |
| `scrape.py` | Harvest all standards and files from official NZQA pages. |
| `enrich.py` | Add files from subject pages and per-standard pages. |
| `fix_and_prune.py` | Fix hosts, keep only PDFs, check every PDF, drop dead links. |
| `focus.py` | Keep only external papers/schedules; drop internals, Māori-medium subjects, Scholarship and subjects with no resources; split L3 Maths into Calculus/Statistics. |
| `add_missing.py` | Add subjects/papers the main scrape misses (schedule-only subjects, Pacific languages, LitNum, newly published files). |
| `build.py` | Render the site from the cleaned data. |
| `verify.py` | Check that the result is PDF-only, linked and complete. |
| `test_links.py` | Rotating live spot-check: fetch 30 random PDFs (required unless `SKIP_LINK_SAMPLE=1`). |
| `rebuild_all.sh` | Runs the full pipeline in order. |
| `verify_ui.js` | Optional behavioural smoke test for the picker (needs jsdom). |
| `data/subjects.json` | Cleaned data (the source for the site). |
| `data/link_report.json` | Per-URL HTTP status from the link check. |
| `data/baseline.json` | Snapshot of subjects/standards; verify fails if any disappear. |
| `make_baseline.py` | Deliberately refresh that snapshot after a legitimate NZQA change. |
| `index.html`, `app.js`, `styles.css` | Three-step picker (level → subject → standard). |
| `all.html` | Complete plain list of all PDFs. |
| `subjects/<slug>/index.html` | Static PDF list per subject. |
| `privacy.html`, `accessibility.html`, `disclaimer.html` | Generated legal/notices pages; do not hand-edit. |
| `friendly.json` | Shared label-cleaning rules used by both renderers. |

## Rebuild

```bash
cd ncea-papers
../.venv/bin/pip install beautifulsoup4
../.venv/bin/python scrape.py        # network, ~15 min
../.venv/bin/python enrich.py        # network, ~12 min
../.venv/bin/python fix_and_prune.py # network, checks every PDF
../.venv/bin/python focus.py         # papers + schedules only
../.venv/bin/python add_missing.py   # schedule-only external subjects
../.venv/bin/python build.py
../.venv/bin/python verify.py
../.venv/bin/python test_links.py    # rotating live spot-check (required unless SKIP_LINK_SAMPLE=1)
npm install --no-save jsdom@22       # once, for the UI smoke test
node verify_ui.js                    # behavioural checks (required unless SKIP_UI=1)
```

Open `index.html` directly, or run `python3 -m http.server 8000` in this folder.

UI regression test (Node + jsdom, installed locally via `package.json`):
`node verify_ui.js` runs 22 behavioural checks. `rebuild_all.sh` installs jsdom if
needed and treats this test as required; set `SKIP_UI=1` to opt out offline.
The link sample is also required unless `SKIP_LINK_SAMPLE=1` is set.

## Notes

- NZQA removes older external resources under a rolling policy, so the index
  covers **2021–2026** (strongest for recent years). Older files are included
  where NZQA still hosts them; see the
  [policy](https://www2.nzqa.govt.nz/ncea/subjects/past-exams-and-exemplars/removal-of-older-resources/).
- Public papers may be redacted for copyright reasons.
- This is an unofficial index, not affiliated with NZQA.
