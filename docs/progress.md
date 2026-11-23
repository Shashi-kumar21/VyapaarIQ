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
- 2026-11-23 · DEV · Rule 3 gating (QA item 7): low-confidence invoice total/buyer/dates/GST never used in calculations or buyer creation; forecast lists unverified amounts as excluded; drafts and dispute pack show "[amount to be verified]" + VERIFY · 84 tests green
- 2026-11-23 · DEV · Evidence graph labels gated on confidence ("? (verify)"), Indian grouping via app.fmt, graph threshold from config; negative-total interest reason (QA follow-ups to 981ede4) · 87 tests green
- 2026-11-23 · DEV · `docs/api_contract.md` v1.0 from the running API (all 14 endpoints incl. new `/api/actions`, doc_types validation, real example JSON, enums, errors, rule-3 behaviour); pending A0/owner sign-off (T1.2)
- 2026-11-23 · DEV · Frontend scaffold (continued from QA branch 95df802): Tailwind v4 wired, routes for Dashboard / New package / Invoice detail / Buyers, API client with VITE_API_BASE + error handling, INR/date helpers, demo banner, backend status (T1.14) · vitest 9 passed, lint + build clean
- 2026-11-23 · DEV · Dashboard on real API (receivables, cash at risk 30/60 with formula, tiers, top 5 actions, invoice table) + New package page (drag-drop, per-file type, buyer hint, upload → process → redirect, error states); QA nits: half-even INR, strictPort, status chip on phones (T1.15, T1.16, T3.11, T3.13) · vitest 17 passed, lint + build clean, browser E2E on PKG07/PKG01
- 2026-11-23 · DEV · Evaluation: eval/run_eval.py + eval/report.md over 28 packages (text: 93.5 % fields exact, 0 confidently wrong, detection P 100 % / R 88.5 %, package verdicts 24 correct + 4 abstained + 0 wrong, due 27/28, median 12 ms; fixture 100 %). Fixed 2 text-extractor bugs it found (truncated IRN trusted, stamp digits in received-by) (T2.7, T5.1, T5.2) · pytest 102
