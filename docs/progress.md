# Progress log

One line per finished task: date · owner · what · verification.

- 2026-11-23 · DEV_N · Day 0 setup: CLAUDE.md, .gitignore, Python 3.13 venv, requirements · `pytest` runs
- 2026-11-23 · DEV_N · Frozen contracts `backend/app/schemas.py` (v1.0) + `rules/config.yaml` (VERIFY markers on legal/rate values)
- 2026-11-23 · DEV_N · Due date, interest, score with unit tests (T1.11-T1.13) · 15 tests
- 2026-11-23 · DEV_N · Synthetic generator: 28 packages, 133 PDFs, 5 scan-style, ground_truth.json with expected checks + due dates (T1.7, T1.8, T2.6)
- 2026-11-23 · DEV_N · Engine: normalisation, checks C01-C14, evidence graph, ranked actions, pipeline (T2.8-T2.12, T3.2)
- 2026-11-23 · DEV_N · Extraction: PyMuPDF text, classifier, fixture/text/claude extractors, fallback chain with "demo fallback" flag (T1.9, T1.10, T2.1-T2.5, T4.8)
- 2026-11-23 · DEV_N · Ground-truth tests: fixture mode reproduces all 28×14 expected checks + due dates; text mode exact on digital docs, `uncertain` (never wrong) on scans · 32 tests green
