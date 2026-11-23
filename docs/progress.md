# Progress log

One line per finished task: date · owner · what · verification.

- 2026-11-23 · DEV_N · Day 0 setup: CLAUDE.md, .gitignore, Python 3.13 venv, requirements · `pytest` runs
- 2026-11-23 · DEV_N · Frozen contracts `backend/app/schemas.py` (v1.0) + `rules/config.yaml` (VERIFY markers on legal/rate values)
- 2026-11-23 · DEV_N · Due date, interest, score with unit tests (T1.11-T1.13) · 15 tests
- 2026-11-23 · DEV_N · Synthetic generator: 28 packages, 133 PDFs, 5 scan-style, ground_truth.json with expected checks + due dates (T1.7, T1.8, T2.6)
- 2026-11-23 · DEV_N · Engine: normalisation, checks C01-C14, evidence graph, ranked actions, pipeline (T2.8-T2.12, T3.2)
- 2026-11-23 · DEV_N · Extraction: PyMuPDF text, classifier, fixture/text/claude extractors, fallback chain with "demo fallback" flag (T1.9, T1.10, T2.1-T2.5, T4.8)
- 2026-11-23 · DEV_N · Ground-truth tests: fixture mode reproduces all 28×14 expected checks + due dates; text mode exact on digital docs, `uncertain` (never wrong) on scans · 32 tests green
- 2026-11-23 · DEV_N · QA_N early review fixes: MSMED limits only for micro/small, unreadable terms -> uncertain, interest not computable without due date, input validation, scoring tests on fixed config (schema 1.1)
- 2026-11-23 · DEV_N · SQLite tables, FastAPI routes (packages/process/invoices/graph/buyers/profile), duplicate detection against DB, error handling with partial results (T1.3, T1.5, T3.1, T3.3, T3.4, T3.6, T4.5) · 59 tests green
- 2026-11-23 · DEV · Seed history (60 synthetic paid invoices, Reliable/Mixed/Slow buyers), follow-up drafts D-7..D+25 friendly/firm email/WhatsApp, cash-at-risk forecast 30/60, dispute pack MD+PDF with MD fallback, routes `/followups`, `/dispute-pack`, `/forecast` (T3.5, T4.1-T4.4) · 70 tests green
