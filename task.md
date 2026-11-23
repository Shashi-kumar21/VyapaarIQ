# VyapaarIQ — Project Tasks (5 days)

Legend: `[ ]` todo · `[~]` in progress · `[x]` done
Owners: **A0** Architect · **A1** Document intelligence · **A2** Backend & risk · **A3** Frontend & QA
Spec: see `BUILD_SPEC.md`. Section numbers (§) refer to it.

**Time budget rule:** ~70% of effort goes to extraction + matching + scoring working reliably. A polished UI over a flaky engine loses to a plain UI over a correct engine.

---

## Day 0 (before Day 1, 30–45 min) — Setup, A0 + you

- [ ] T0.1 Install Claude Code on Windows (`irm https://claude.ai/install.ps1 | iex`), run `claude --version`
- [ ] T0.2 Confirm Agent Bridge works with 4 terminals (A0–A3); do one ping-pong message test
- [ ] T0.3 Decide `ANTHROPIC_API_KEY` availability (API credit is separate from Claude Pro). If none, default `EXTRACTOR=text` + `fixture`
- [~] T0.4 Create repo `vyapaariq`, add `BUILD_SPEC.md`, `task.md`, `.gitignore`, one branch per agent
- [x] T0.5 Write `CLAUDE.md` (project rules for all agents): stack, ownership table (§17), commands to run/test, "deterministic first, LLM second", no secrets in git
- [x] T0.6 Verify toolchain: Python 3.11+, Node 20+, `pip install fastapi uvicorn sqlmodel pymupdf pydantic reportlab pyyaml rapidfuzz python-multipart pytest anthropic`, `npm create vite@latest`

**Gate 0:** four agents running, repo cloned, each agent has read `CLAUDE.md`.

---

## Day 1 — Foundation and contracts

### A0 Architect
- [x] T1.1 Write `backend/app/schemas.py`: Pydantic models for all doc types (§6), `Check`, `Action`, `Graph`, `Invoice` — **freeze by midday**
- [x] T1.2 Write `docs/api_contract.md` (§12) with example JSON for every endpoint
- [x] T1.3 `backend/app/db`: SQLModel tables (§5), `init_db()`, session helper
- [x] T1.4 `rules/config.yaml` skeleton: tolerances, penalties, thresholds, 45/15-day rules, e-way threshold, bank rate placeholder (marked VERIFY)
- [x] T1.5 FastAPI app skeleton with `/api/health`, CORS, routers stubbed with fixture responses so frontend can start immediately
- [ ] T1.6 Message A1/A2/A3 when contracts are frozen

### A1 Document intelligence
- [x] T1.7 `samples/generate.py` v1: reportlab generator for invoice, PO, challan, e-way, GRN with fictional companies
- [x] T1.8 Defect injector + `ground_truth.json` writer (§14); generate first 10 packages
- [x] T1.9 `extraction/pdf_text.py`: PyMuPDF text + page-image extraction; detect "scanned" (low text) PDFs
- [x] T1.10 `extraction/base.py`: `Extractor` interface; `fixture` extractor reading ground truth

### A2 Backend & risk
- [x] T1.11 `rules/due_date.py`: acceptance date, deemed acceptance, due date with reasoning string (§7) + unit tests
- [x] T1.12 `rules/interest.py`: monthly-compounded 3× bank-rate estimate + unit tests
- [x] T1.13 `scoring/score.py`: penalties → score → tier from config + unit tests

### A3 Frontend & QA
- [x] T1.14 Vite + React + Tailwind scaffold, routing for 4 pages (§13), API client with base URL env
- [ ] T1.15 Dashboard page with mocked data; INR formatting helper (₹2,40,000)
- [ ] T1.16 New-package upload page (drag-and-drop, file list, doc-type dropdown, Process button wired to stub)

**Gate 1:** `uvicorn` serves stub API; frontend shows mocked dashboard + upload page; 10 sample packages exist; due-date/interest/score unit tests pass.

---

## Day 2 — Document intelligence

### A1
- [x] T2.1 `llm/client.py`: Claude client reading `ANTHROPIC_API_KEY`, `LLM_MODEL` from env; timeout, one retry, JSON-only parsing, fenced-JSON stripping
- [x] T2.2 `llm/prompts.py`: extraction prompts per doc type (§6 rules: null for unknown, ISO dates, confidence per field)
- [x] T2.3 `extraction/claude_extractor.py`: text-first, image fallback for scanned docs; Pydantic validation; retry once on schema failure
- [x] T2.4 `extraction/text_extractor.py`: regex/heuristic fallback for digital PDFs (invoice no., dates, GSTIN, totals)
- [x] T2.5 Doc-type classifier (filename hints + first-page keywords + LLM fallback)
- [x] T2.6 Generate full 25–30 package set with scan-style variants (§14); commit `ground_truth.json`
- [ ] T2.7 Quick accuracy script: per-field accuracy on first 10 packages; log failures

### A2
- [x] T2.8 `matching/normalize.py`: party-name normalisation (strip Pvt/Ltd/punctuation), GSTIN validation (15-char format + checksum optional), date/amount parsing
- [x] T2.9 `matching/checks.py`: implement C01–C04 with tests (§7)
- [x] T2.10 `matching/checks.py`: implement C05–C08 with tests
- [x] T2.11 `matching/checks.py`: implement C09–C14 with tests
- [x] T2.12 `matching/graph.py`: build evidence graph JSON from docs + check results (§12)

### A3
- [ ] T2.13 Invoice detail page skeleton: header, checks list with severity chips, tabs (Graph / Actions / Follow-ups / Dispute pack)
- [ ] T2.14 `EvidenceGraph` component (SVG or React Flow) driven by `/graph` JSON; node status colours + icons (ok / missing / mismatch / uncertain), edge labels
- [ ] T2.15 Extracted-fields panel showing confidence and "needs human check" amber state
- [ ] T2.16 Start `eval/run_eval.py` harness shell (loads ground truth, calls pipeline, writes report)

**Gate 2:** For ≥10 sample packages, pipeline (using `fixture` or real extractor) yields correct check results; evidence graph renders for a real package JSON.

---

## Day 3 — Intelligence engine

### A2
- [x] T3.1 `POST /api/packages`, `/process`, `GET /packages/{id}` wired to real extraction → checks → score → DB
- [x] T3.2 `scoring/actions.py`: action templates per check, ranking by severity then deadline (§7 Actions)
- [x] T3.3 `GET /api/invoices`, `/invoices/{id}`, `/graph` returning real data
- [x] T3.4 Duplicate-invoice detection against DB (C14) end-to-end
- [x] T3.5 `seed.py`: supplier, 6 buyers, ~60 historical invoices with payment events (synthetic; flagged)
- [x] T3.6 `GET /api/buyers/{id}/profile` per §8 with min-history rule + tests

### A1
- [ ] T3.7 Run extraction over all packages; fix top 5 failure patterns (prompt tweaks, normalisation, layout handling)
- [ ] T3.8 LLM explanation writer: takes check result + facts → 2-sentence plain-English explanation (cannot change status/score); cache results
- [x] T3.9 Confidence calibration: threshold below which a field is "uncertain" and the check becomes `uncertain` rather than pass/fail
- [ ] T3.10 Processing-time logging per package

### A3
- [ ] T3.11 Wire upload → process → redirect to invoice detail with progress states (uploading / extracting / checking / done / failed)
- [ ] T3.12 Actions tab (ranked list, due-by, rationale) and score breakdown panel (each penalty listed)
- [ ] T3.13 Dashboard on real `/invoices` data: tiers, open receivables, top actions
- [ ] T3.14 Buyers page with reliability numbers (labelled synthetic demo data)

**Gate 3:** Upload a package in the UI → real graph, checks, score, actions. Clean package scores ≥85; "GRN missing" package shows blocker + correct action.

---

## Day 4 — Complete application

### A2
- [x] T4.1 `followups`: generate D−7 / D−1 / D+3 / D+10 / D+25 drafts, friendly/firm tones; deterministic templates, LLM polish optional (§10)
- [x] T4.2 `POST /invoices/{id}/followups/generate`, `GET` list
- [x] T4.3 `forecast/cash_at_risk.py` + `GET /api/forecast` (§9) + tests
- [x] T4.4 `dispute/pack.py`: Markdown template → PDF (§11); `GET /invoices/{id}/dispute-pack`
- [x] T4.5 Error handling: corrupt PDF, empty upload, unsupported type, extractor failure → clear API errors, partial results kept

### A1
- [ ] T4.6 Edge cases: rotated scans, multi-invoice PDF, two documents in one file, Hindi/mixed-language stamps (best effort; log what fails)
- [ ] T4.7 Re-run extraction accuracy on all packages; record numbers
- [x] T4.8 Fixture fallback switch: if Claude extractor fails or key missing, auto-fall back to `text`, then `fixture` (with a visible "demo fallback" badge)

### A3
- [ ] T4.9 Follow-ups tab (draft cards, copy button, tone toggle; clearly "draft, not sent")
- [ ] T4.10 Dispute pack tab (preview + download)
- [ ] T4.11 Dashboard forecast chart (30/60-day buckets) with formula tooltip
- [ ] T4.12 Empty/loading/error states on every page; "illustrative risk, demo data" banners
- [ ] T4.13 Full run-through of all packages in the UI; log bugs in `docs/bugs.md` with owner tag

### A0
- [ ] T4.14 Integration review: merge branches, resolve conflicts, run full test suite, fix cross-module contract bugs
- [ ] T4.15 `README.md`: setup ≤5 commands, env vars, `EXTRACTOR` modes, how to run seed/eval

**Gate 4:** Entire flow works in the UI on real packages including follow-ups, forecast, dispute pack. No P0 bugs open.

---

## Day 5 — Evaluation, hardening, demo

### A3 + A1
- [ ] T5.1 Complete `eval/run_eval.py`: field accuracy, check precision/recall, due-date correctness, median time (§15)
- [ ] T5.2 Run eval on all 25–30 packages; write honest `eval/report.md` incl. failure cases
- [ ] T5.3 Fix highest-impact failures from the report (time-boxed: 2 hours max)

### A2
- [ ] T5.4 Backend tests green; add regression tests for each bug fixed this week
- [ ] T5.5 Performance pass: package processing < 60 s; cache LLM calls; avoid re-extracting unchanged files
- [ ] T5.6 Review rule config values against current law/portal process (MSMED s.15/16, 43B(h), ODR portal route, RBI bank rate); update `config.yaml` and the dispute-pack wording

### A3
- [ ] T5.7 UI polish: spacing, typography, status colours, mobile-width sanity, consistent INR formatting
- [ ] T5.8 `docs/demo_script.md` (3 minutes, see below); record a backup screen recording
- [ ] T5.9 Fresh-clone test on a clean folder following `README.md` exactly

### A0
- [ ] T5.10 Final merge, tag `v0.1-demo`, remove debug logs, confirm no secrets/API keys in git history
- [ ] T5.11 `docs/architecture.md` (one diagram + one page) and a short pitch slide or README section: problem, solution, metrics, limits, next steps

**Gate 5 = Definition of Done (BUILD_SPEC §18).**

---

## 3-minute demo script (draft)

1. **0:00–0:30** Problem: delayed payments, one real stat (verify the figure and source on the day), owner-with-WhatsApp-and-Excel picture.
2. **0:30–1:30** Upload a package where GRN is missing → graph builds live → "Buyer acceptance missing" blocker → score drops → recommended action with date.
3. **1:30–2:15** Open follow-up drafts (friendly vs firm); show due-date reasoning and estimated statutory interest.
4. **2:15–2:45** Dashboard: cash at risk next 30/60 days; buyer reliability table (state it is seeded demo history).
5. **2:45–3:00** Eval numbers from `eval/report.md`, honest limits, what comes next (accounting-software sync, WhatsApp sending, ODR filing support).

---

## Daily rhythm (all agents)

- **Start of day:** A0 posts the day's goals; agents confirm ownership, no overlapping files.
- **Midday:** 10-min sync via Agent Bridge — blockers, contract changes only.
- **End of day:** each agent commits + pushes its branch, ticks `task.md`, adds a one-line note to `docs/progress.md`; A0 merges and runs tests; fix broken merges before sleeping.

## Prompts to start each agent (copy into the terminals)

**A0:** "Read BUILD_SPEC.md and task.md. You are A0 Architect. Do Day 0 and Day 1 A0 tasks first. Freeze schemas.py and api_contract.md, then notify other agents. You own merges."

**A1:** "Read BUILD_SPEC.md and task.md. You are A1 Document intelligence. Only edit backend/app/extraction, backend/app/llm, samples/. Start with the synthetic sample generator and ground truth, then extraction. Do not edit other folders; request contract changes from A0."

**A2:** "Read BUILD_SPEC.md and task.md. You are A2 Backend & risk. Only edit backend/app/{api,matching,rules,scoring,forecast,dispute} and backend/tests. Deterministic logic first, with unit tests for every rule. Never let LLM output change a score."

**A3:** "Read BUILD_SPEC.md and task.md. You are A3 Frontend & QA. Only edit frontend/, eval/, docs/demo_script.md. Build against api_contract.md using mocked data until real endpoints land. Prioritise the Invoice detail page and Evidence Graph."

## If you fall behind — cut list (in order)
1. Forecast chart → keep numbers table only.
2. PDF export → Markdown download.
3. Buyers page → show profile inside invoice detail.
4. Scan-style sample variants → digital PDFs only (say so).
5. LLM explanations → template explanations.
**Never cut:** extraction, checks C01/C05/C06/C10, evidence graph, score breakdown, eval report.
