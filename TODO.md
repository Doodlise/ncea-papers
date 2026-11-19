# User requests — tracked

Legend: [x] done and verified · [~] in progress · [ ] not started

## Site / scope
- [x] Barebones site covering NCEA externals at Levels 1, 2, 3 (English-medium subjects with papers or schedules; Māori-medium excluded).
- [x] Work continuously, no stopping, no questions.
- [x] Use subagents to review changes and gather information.
- [x] Manually review every function; reiterate and deploy many subagents.
- [x] Keep the original goal in mind while making later changes.
- [x] Broad coverage — 52 subjects with papers or schedules (not STEM-only).
- [x] Every included subject must actually have past papers or answer schedules.
- [x] Only external assessment — no internals.
- [x] Remove internal-only subjects and useless documents.
- [x] Only past papers and answer schedules (no exemplars, reports, specs, PEPs, standard docs).
- [x] Papers up to date — 2021–2026.
- [x] Scholarship researched: only 4 real exam PDFs exist; not enough, so cut out completely.

## Links
- [x] Fix mass 404s — wrong host (www2 for /nqfdocs/); now www for PDFs, www2 for /assets/.
- [x] Explain cause of the 404s with curl evidence.
- [x] Every link goes directly to a PDF — enforced in data, renderer and verifier.
- [x] Use view-detailed.do pages as the source for all papers/schedules.
- [x] Actually tested: browser click-through + live HTTP samples (30/30, 50/50).

## UI / UX
- [x] Fix cluttered layout — simple 3-step picker.
- [x] No year slider; choose the external and see all its resources.
- [x] Group resources by year, each year in its own box.
- [x] Consistent formatting and student-friendly wording.
- [x] Remove the "What it is" column.
- [x] Dynamic step-3 wording fixed; no Māori translations.
- [x] Mobile-safe CSS.
- [x] Dark mode.
- [x] Show the to-do list here in OpenCode (not on the website).
- [x] Subjects listed alphabetically at every level.
- [x] Student-friendly link wording on generated pages too; viewport meta on all subject pages; aria-live status; one-column PDF tables.

## Content / naming
- [x] Subject names across levels: L1/L2 "Mathematics and Statistics"; L3 explicitly SPLIT into separate "Calculus" and "Statistics" subjects (91577–91579 → Calculus, 91584–91586 → Statistics), per user's repeated correction.
- [x] Added DVC, Technology and Visual Arts (schedule-only externals) for consistent coverage.
- [x] Added-subject metadata refreshed (live PDF check, titles, focus_report) and docs corrected.
- [x] Researched other naming cases; misplaced standards moved to their own subjects (Home Economics, Art History, PESS, AgHort, ChemBio, NZSL, MPT).
- [x] Fixed P0 bug where three subjects' standards were silently dropped; verified idempotent.

## Verification
- [x] Removed sample-assessment PDFs (-sxp-, -sas-) that slipped through as "papers".
- [x] Merged duplicate "Gagana Sāmoa"/"Samoan" subject into one.
- [x] Removed duplicate standard entries within subjects.
- [x] Added verify checks so none of the above can regress.
- [x] Dead links dropped; all included PDFs checked against NZQA.
- [x] verify.py checks PDF-only, external-only, papers-only, naming consistency, broad coverage.
- [x] Pipeline reproducible: scrape → enrich → prune → focus → add_missing → build → verify.
- [x] Final rebuild passed; browser test and 30/30 live sample passed.
- [x] Applied audit cleanup: docs accurate, pipeline guard, idempotent split.
- [x] Removed dead Scholarship/Digital scraping stages and leftover data fields from the pipeline.
- [x] Atomic writes in build.py, safe reads/equality check in verify.py, report-first write in fix_and_prune.py.
- [x] Lighthouse: Accessibility/Best Practices/SEO all 1.00 with zero failures.
- [x] Added 4 newly published Korean 2026 PDFs; add_missing now merges new docs into existing standards and syncs the link report.
- [x] Added 6 missing subject groups (LitNum, Cook Islands Māori, Gagana Tokelau, Lea Faka-Tonga, Te Reo Māori Kūki ‘Āirani, Vagahau Niue) and a missing Art History 2025 schedule.
- [x] Fixed LitNum attribution: 23 more papers/schedules found by attributing files to their per-standard page.
- [x] UX/performance improvements: focus ring, print stylesheet, 677 KB → 411 KB data.js, accessible generated pages, clearer labels and new-tab/partial-year notes.
- [x] Data quality: real NZQA titles/credits for 46 standards, 17 more LitNum papers (questions-public), 19 years recovered, schema metadata completed.
- [x] Fresh-pipeline reproducibility confirmed: current code produces 52 subjects; shipped data has 2,726 PDFs after removing 8 LitNum translation PDFs in total.
- [x] add_missing now refreshes titles/credits when merging into an existing standard.
- [x] Duplicate link labels disambiguated (1 of 2 / 2 of 2); picker shows subject/standard counts and last-checked date; link sample rotates each run.
- [x] Picker and generated pages now use identical link ordering (1194 year boxes, 0 mismatches) and aligned label-cleanup regexes.
- [x] Static pages: consistent h4 year headings, intro/date/offline notes, level jump nav, subject links from all.html, All PDFs navigation, print fixes.
- [x] Student workflow: standard-number jump, last-selection recall, 44px mobile tap targets, italic answer-schedule cue.
- [x] Robustness: baseline drift detection + deliberate refresh path (make_baseline.py), fetch-error propagation, stage-count/date consistency checks, fatal rotating link sample, transient-error retries.
- [x] Scope accuracy: removed 3 more LitNum translation PDFs (Cook Islands Māori/Niuean/Tokelaun) with verifier guard.
- [x] Navigation: back-to-top links on the long pages; schedule-only standards now explain no paper is listed.
- [x] Ambiguous LitNum "Exam paper (1 of 2)" labels now show a short file qualifier (e.g. "32403A-1"); JS/Python parity verified.
- [x] Consistent schedule-only guidance across picker/static pages, print context retained, verifier checks PDF anchor URLs, dead Scholarship/Digital code removed.
- [x] all.html year headings now h5 (correct nesting), print hides nav, link_report records observed statuses for added PDFs.
- [x] Per-subject-page verifier checks (URLs + labels), hash-based selection recall for file://, 44px nav tap targets, printable PDF URLs.
- [x] Print headings readable, subject-page level nav, NZSL video labels disambiguated, verifier enforces 2026 coverage, malformed-hash guard.
- [x] QOL: per-year file counts, `/` shortcut to number jump, empty-jump guard, file:// hash fallback, shared friendly.json label rules, printable provenance.
- [x] More QOL: live hash links with race guard, stale-selection clearing, back-to-top after results, count in live hint, jump-field auto-select, data-load failure message.
- [x] Robustness: dead subject-page nav anchors removed, label parity guard, anchor-resolution verifier check, atomic subject-tree swap, aligned PDF spot-check.
- [x] Fixed cold-load deep-link/localStorage recall, history pollution, rapid-Back stale UI; added pushState/popstate navigation, atomic full-build writes.
- [x] Fixed undefined `push` variable (pushState never ran), programmatic selections stripping history hash, invalid deep-link feedback, prose jump input, stale back-to-picker state.
- [x] Fixed #picker hash misread as invalid standard, user level/subject changes not clearing saved state, invalid-hash stale results, duplicate jump history, year-prefixed prose jumps.
- [x] Invalid hash/jump now fully resets picker (fixes valid-hash recovery after a typo), Back-to-picker clears saved state, case-insensitive label parity, verifier checks script order/reset invariant.
- [x] #picker/invalid-hash cold loads clear saved selection and strip bad hash; added optional jsdom UI smoke test (now 22 checks, wired into rebuild_all.sh).
- [x] Malformed percent-encoded hash feedback/cleanup, #picker mid-session full reset, global jump-number uniqueness guard.
- [x] Public hosting prepared and deployed: WCAG 2.2 AA review (removed global `/` shortcut), skip links, privacy/accessibility/disclaimer pages, NZQA written attribution, no-referrer, GitHub Pages HTTPS.
- [x] Live at https://doodlise.github.io/ncea-papers/ (Pages build verified, Lighthouse 1.00/1.00/1.00).
- [x] Back-to-picker now uses native hash navigation (browser Back restores the standard); hash shape validation prevents oversized/control-character hints; leading-zero jump input resolved; UI smoke test made fatal in pipeline.
- [x] Local jsdom devDependency + 22 UI smoke checks (adds signed hash, leading zeros, multi-token errors, #picker navigation, picker/static label parity); precompiled label regexes; invalid-token error uses last token.
- [x] UI test truly fatal in pipeline (REQUIRE_UI=1, SKIP_UI opt-out), verifier checks test-surface files, shared PDF-URL validation between picker and renderer, README updated.
- [x] Short-digit jump input echoes the right token; leading-zero deep links normalized; friendly.json patterns validated in both Python and JS; parity sweep now deterministic and compares labels + URLs for all 255 standards.
- [x] Applied top 3 over-engineering cuts: removed harvest-then-discard metadata, note/exemplar collectors, direct-document harvesting (-87 lines); all checks + Lighthouse still pass.
- [x] Post-cut cleanup: legacy fields purged from data (incl. document-level), schema-drift guard, baseline presence guard, dead parse loop removed, per-standard fetch warnings, accurate build byte counts and docs.
- [x] Final guard pass: verifier byte counts, no unverified statuses, date on every generated page, duplicate-slug check, link report scoped to shipped URLs.
- [x] Link-sample SKIP_LINK_SAMPLE opt-out + docs, host normalization in add_missing, HTML-parsed script-order check, case-insensitive #picker deep link.
- [x] Silent-fetch failures now recorded, UI test surface/wiring guarded, brittle source-text checks replaced by the behavioural suite.
- [x] Graceful verification when all.html missing (both suites), exact UI check-count guard, README rebuild recipe includes UI test, transient errors recorded in both link checkers, label casing/#00000 polish.
- [x] Converted raw filename-style labels (mainly LitNum) into student-friendly wording; removed residual "assessment paper"/"Examination audio..." jargon and strengthened verifier.
