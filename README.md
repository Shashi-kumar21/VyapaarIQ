# VyapaarIQ

**Upload an invoice package → build an Invoice Evidence Graph → detect what could block or weaken
payment → explain the risk → recommend the next action → draft follow-ups and a dispute-ready
evidence pack.**

VyapaarIQ is for Indian MSME suppliers who sell on credit. When a buyer pays late or disputes an
invoice, the supplier often can't quickly prove delivery and acceptance, and doesn't know which
invoices are at risk until they are already overdue. VyapaarIQ reads the documents behind each
invoice and cross-checks them. It shows the gaps and works out the MSMED Act timelines.

> **Demo project.** All data is **synthetic** and every company is **fictional**. Risk scores and
> forecasts are *illustrative*. Legal values (45/15-day rules, bank rate, interest) are
> configurable and marked *verify*. **Nothing here is legal advice.**

- What to build: [`BUILD_SPEC.md`](BUILD_SPEC.md) · Plan and owners: [`task.md`](task.md)
- REST API reference: [`docs/api_contract.md`](docs/api_contract.md) · Progress log: [`docs/progress.md`](docs/progress.md)
- Architecture (one page + diagram): [`docs/architecture.md`](docs/architecture.md) · 3-minute demo: [`docs/demo_script.md`](docs/demo_script.md)
- Sources and every design decision (who, when, why): [`docs/references.md`](docs/references.md)
- Full UI run-through of all packages and the bug log: [`docs/bugs.md`](docs/bugs.md)
- Rules for contributors and AI agents: [`CLAUDE.md`](CLAUDE.md)

---

## Contents

1. [Features](#features)
2. [How it works](#how-it-works)
3. [Status](#status)
4. [Requirements](#requirements)
5. [Quick start](#quick-start)
6. [Configuration](#configuration)
7. [Running a demo end to end](#running-a-demo-end-to-end)
8. [Verification checks (C01–C14)](#verification-checks-c01c14)
9. [Due date, interest and score](#due-date-interest-and-score)
10. [API overview](#api-overview)
11. [Project layout](#project-layout)
12. [Testing](#testing)
13. [Design principles](#design-principles)
14. [Security and data handling](#security-and-data-handling)
15. [Contributing workflow](#contributing-workflow)
16. [Known limitations](#known-limitations)

---

## Features

| Feature | What you get |
|---|---|
| Package upload | PDF / PNG / JPG files for one invoice: invoice, PO, delivery challan / LR, e-way bill, GRN / acceptance, contract. Each file's type is auto-detected, or you can set it. |
| Extraction | Structured fields per document. Each field carries `value`, `confidence` and `source_page`. |
| 14 verification checks | Cross-document matching: PO reference, amounts and GST math, line items, buyer identity, delivery proof, quantities, receiving stamp, date order, e-way bill, GRN, payment terms, Udyam, duplicates. |
| Evidence graph | Nodes are the documents and edges show match status (`matched / mismatch / missing / uncertain`). This is the main demo screen. |
| Readiness score | 0–100 with a Low / Medium / High tier. Every penalty is listed. |
| Ranked actions | What to fix first, owner role and a due-by date relative to the due date. |
| Due date and interest | Acceptance date (GRN, signed challan, or deemed), MSMED 45/15-day terms, and estimated s.16 compound interest with the formula shown. |
| Follow-up drafts | D−7, D−1, D+3, D+10 and D+25 drafts in friendly or firm tone, for email or WhatsApp. **Drafts only, never sent.** |
| Buyer reliability | Median days late, % late, % over 30 days late and trend from the supplier's own history (seeded synthetic history for the demo). |
| Cash-at-risk forecast | 30 / 60-day view with buckets, a transparent formula and the excluded invoices listed. |
| Dispute evidence pack | PDF (with a Markdown fallback): timeline, document index, checks, due-date reasoning, interest estimate, missing evidence and the suggested next step (MSME ODR portal, verify). |

## How it works

```
 files ──▶ classify ──▶ extract ──▶ 14 checks ──▶ score + tier ──▶ actions
 (PDF/img)  (keywords,   (claude │     (deterministic    (config)        │
            filename,     text │      Python)                           ▼
            user)         fixture)        │                     follow-ups, forecast,
                                          ▼                     dispute pack
                                 due date + interest
                                 evidence graph ──▶ SQLite ──▶ REST API ──▶ React UI
```

1. **Upload** creates a *package*. Files are stored locally and classified.
2. **Process** extracts each file, runs checks C01–C14, computes the score, due date, interest,
   actions and graph, then stores everything. If one file fails, the others are still processed
   and kept.
3. The **API** serves the results to the frontend. Follow-ups, the forecast and the dispute pack
   are built on demand from the stored analysis.

## Status

| Area | State |
|---|---|
| Rules: due date, deemed acceptance, 45/15-day terms, s.16 interest | ✅ tested |
| Checks C01–C14, readiness score, ranked actions, evidence graph | ✅ tested against ground truth |
| Confidence gating (low-confidence values never used in calculations) | ✅ tested |
| Extraction: `text` (PyMuPDF + regex), `fixture`, `claude` (optional) | ✅ (claude path tested offline only) |
| Synthetic generator: 28 packages / 133 PDFs, 5 phone-scan style | ✅ |
| REST API + SQLite: packages, invoices, graph, actions, buyers, forecast | ✅ tested |
| Seed history, follow-up drafts, forecast, dispute pack | ✅ tested |
| API contract ([`docs/api_contract.md`](docs/api_contract.md)) | ✅ v1.0 |
| React frontend: dashboard, upload, invoice detail + evidence graph, follow-ups, dispute pack, buyers | ✅ tested (vitest unit/component tests + manual browser run-through) |
| Evaluation script and report ([`eval/report.md`](eval/report.md)) | ✅ `text`: 0 confidently wrong fields, detection precision 100 % |

## Requirements

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ (the venv uses 3.13) | Backend |
| Node.js | 20+ | Frontend |
| Git | any recent | |
| Anthropic API key | optional | Only for `EXTRACTOR=claude`. API credit is billed separately from a Claude Pro plan. |

Python packages are listed in [`backend/requirements.txt`](backend/requirements.txt): FastAPI,
Uvicorn, SQLModel, Pydantic, PyMuPDF, reportlab, PyYAML, rapidfuzz, python-multipart, Pillow,
anthropic, pytest, httpx.

## Quick start

### Windows (PowerShell), from the repo root

```powershell
# 1. Backend environment
py -3.13 -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt

# 2. Synthetic sample packages (writes samples/out/; ground_truth.json is committed)
.\.venv\Scripts\python samples\generate.py

# 3. Tests
cd backend; ..\.venv\Scripts\python -m pytest -q

# 4. Seed synthetic buyer payment history (needed for buyer profiles and the forecast)
..\.venv\Scripts\python -m app.seed            # add --reset to rebuild

# 5. Run the API: http://127.0.0.1:8000 (interactive docs at /docs)
..\.venv\Scripts\uvicorn app.main:app --reload
```

Frontend (in a second terminal):

```powershell
cd frontend; npm install; npm run dev          # UI on http://localhost:5173
```

### macOS / Linux

Run the same steps with `python3 -m venv .venv` (Python 3.11+) and `.venv/bin/pip`,
`.venv/bin/python` and `.venv/bin/uvicorn` instead of `.\.venv\Scripts\...`.

## Configuration

### Environment variables

Copy [`.env.example`](.env.example) to `.env` and set only what you need. Never commit `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `EXTRACTOR` | `text` | `claude` \| `text` \| `fixture`. Falls back automatically along `claude → text → fixture`. |
| `ANTHROPIC_API_KEY` | – | Needed only for `EXTRACTOR=claude`. `ANTHROPIC_AUTH_TOKEN` is also accepted in its place. |
| `LLM_MODEL` | `claude-opus-5-5` | Model id for the `claude` extractor. Check it against current Anthropic docs. |
| `LLM_EFFORT` | `medium` | `low` \| `medium` \| `high`. |
| `VYAPAARIQ_DB` | `backend/data/vyapaariq.db` | SQLite file path. |
| `VYAPAARIQ_TODAY` | today | Pins "today" (`YYYY-MM-DD`) for reproducible demos. It affects due dates, interest, forecast and past drafts. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed to call the API. |
| `GROUND_TRUTH` | `samples/ground_truth.json` | Ground-truth file used by the `fixture` extractor. |
| `VYAPAARIQ_LOG_LEVEL` | `INFO` | App log level (case-insensitive; an unknown name falls back to INFO with a warning). At `INFO` each processed package logs one line: ids, document count, extractor and time in ms. Document text is never logged. |
| `VITE_API_BASE` | `http://localhost:8000` | Frontend: base URL of the API. |

### Extractor modes

| Mode | What it does | Needs |
|---|---|---|
| `text` (default) | PyMuPDF text layer plus regex heuristics. Scanned pages come back *uncertain*. | nothing |
| `claude` | Claude reads the text (or the PDF/image for scans) and returns validated JSON. | `ANTHROPIC_API_KEY`, optional `LLM_MODEL` |
| `fixture` | Reads `samples/ground_truth.json`, so the demo runs offline. | nothing |

Anything produced by a fallback is flagged `fallback: true`, and the UI shows a **"demo
fallback"** badge for it.

### Rule values

Every tolerance, penalty, threshold and legal parameter lives in
[`backend/app/rules/config.yaml`](backend/app/rules/config.yaml). None of them are hard-coded.

| Key | Default | Meaning |
|---|---|---|
| `supplier.enterprise_class` | `small` | MSMED s.15/16 apply only to `micro` / `small`. |
| `msmed.max_terms_days` / `no_agreement_days` | 45 / 15 | s.15 limits. |
| `msmed.deemed_acceptance_offset_days` | 0 | Deemed acceptance = delivery date + N days. 0 follows MSMED s.2(b): the delivery day itself when there is no written objection within 15 days (**verify** against the Act). |
| `rbi.bank_rate_pct` | 5.75 (as of 2026-10-07) | **Verify** the current RBI bank rate before a demo. Interest uses 3× this rate. |
| `extraction.uncertain_below` | 0.60 | Fields read below this confidence are `uncertain` and never used in calculations. |
| `scoring.penalties` | blocker 25 (C10 = 30), warning 10, uncertain 5 | Score = 100 − Σ penalties. |
| `scoring.tiers` | Low ≥ 85, Medium 60–84, High < 60 | |
| `eway.threshold_inr` | 50,000 | C09 e-way bill requirement. |
| `buyer_profile.min_history` | 5 | Fewer paid invoices → "Insufficient history". |
| `followups.steps` | −7, −1, 3, 10, 25 | Days relative to the due date. |

## Running a demo end to end

With the API running (and `EXTRACTOR=fixture` and `VYAPAARIQ_TODAY=2026-11-23` for reproducible
numbers):

```bash
# upload the "GRN missing" package
curl -F "files=@samples/out/PKG07/PKG07_invoice.pdf" -F "files=@samples/out/PKG07/PKG07_po.pdf" \
     -F "files=@samples/out/PKG07/PKG07_challan.pdf" http://127.0.0.1:8000/api/packages
# -> {"id": <package_id>, ...}

curl -X POST http://127.0.0.1:8000/api/packages/<package_id>/process   # -> {"invoice_id": ..., "status": "done"}
curl http://127.0.0.1:8000/api/invoices/<invoice_id>             # checks, score, due date, actions, graph
curl -X POST "http://127.0.0.1:8000/api/invoices/<invoice_id>/followups/generate?tone=firm"
curl -o pack.pdf http://127.0.0.1:8000/api/invoices/<invoice_id>/dispute-pack
curl "http://127.0.0.1:8000/api/forecast?days=30"
```

Sample packages `PKG01`–`PKG28` each have a known defect (or none). See
`samples/ground_truth.json`:

| Packages | Injected defect |
|---|---|
| PKG01–06 | clean |
| PKG07–08 | missing GRN |
| PKG09–10 | missing challan |
| PKG11–12 | quantity short on challan |
| PKG13–14 | invoice above PO value |
| PKG15–16 | buyer name / GSTIN mismatch |
| PKG17–18 | missing PO reference |
| PKG19–20 | terms over 45 days |
| PKG21–22 | no stamp on challan |
| PKG23–24 | duplicate invoice number |
| PKG25–26 | wrong GST math |
| PKG27 | missing GRN + no stamp |
| PKG28 | terms over 45 days + missing PO reference |

## Verification checks (C01–C14)

Each check returns a `status` (`pass / fail / missing / uncertain`), a `severity`, a plain-English
`detail` and the evidence it used. A check that depends on a field read with low confidence
returns `uncertain` rather than guessing.

| ID | Check | Fails when | Severity |
|---|---|---|---|
| C01 | Invoice ↔ PO reference | no PO ref, PO not in package, or numbers differ | blocker |
| C02 | Amount reconciliation | taxable > PO value + 1 %, or taxable + GST ≠ total (± ₹1) | blocker |
| C03 | Line items vs PO | qty / rate above PO beyond tolerance | warning / blocker |
| C04 | Party consistency | buyer name / GSTIN differ across documents | blocker |
| C05 | Delivery proof exists | no challan / LR | blocker |
| C06 | Delivered ≥ invoiced qty | challan qty < invoice qty | blocker |
| C07 | Receiving evidence | no receiver stamp or signature on challan | warning |
| C08 | Date logic | challan > N days after invoice, or PO dated after invoice | warning |
| C09 | E-way bill | value above threshold and no / mismatched e-way bill | warning |
| C10 | GRN / acceptance | no GRN or written acceptance | blocker |
| C11 | Payment terms defined | no written terms (15-day rule applies) | warning |
| C12 | Terms ≤ 45 days | terms > 45 days for a micro/small supplier | warning |
| C13 | Supplier Udyam present | no Udyam number on supplier documents | info |
| C14 | Duplicate invoice | same invoice no. + buyer already on record | blocker |

## Due date, interest and score

- **Acceptance date** is the GRN date if there is one, otherwise the received date on the
  delivery challan, otherwise *deemed* acceptance (the delivery date, per MSMED s.2(b); configurable and labelled
  "deemed / estimated").
- **Due date** is acceptance + min(written terms, 45) days, or acceptance + 15 days when there are
  no written terms. The 45-day cap and the 15-day default are MSMED rules for micro/small
  suppliers. For a `medium` supplier, written terms apply as written, and without written terms
  15 days is only an assumption (marked `uncertain`). The response always states which rule
  produced the date.
- **Interest** is an estimate of MSMED s.16 interest: compound with monthly rests (full 30-day
  months compound, and the remaining days accrue pro rata) at 3 × the RBI bank rate, on the delay
  beyond the due date. The formula is returned with the number.
- **Score** is 100 − Σ penalties, clamped to 0–100, with tiers from config. It is an illustrative
  readiness score, not a prediction of whether the buyer will pay.

## API overview

All paths start with `/api`. Request and response shapes, enums, error codes and example JSON are
in **[`docs/api_contract.md`](docs/api_contract.md)**.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness, schema version, extractor mode, demo date |
| POST | `/api/packages` | Upload files (`multipart/form-data`) |
| POST | `/api/packages/{id}/process` | Extract → checks → score → store |
| GET | `/api/packages/{id}` | Package, documents, extracted fields |
| GET | `/api/invoices` | Invoice list (filters: `tier`, `buyer_id`, `status`, `include_history`) |
| GET | `/api/invoices/{id}` | Invoice + full analysis + documents |
| GET | `/api/invoices/{id}/graph` | Evidence graph |
| GET | `/api/actions?limit=5` | Top open actions across invoices |
| POST | `/api/invoices/{id}/followups/generate` | (Re)generate drafts (`tone`, `channel`) |
| GET | `/api/invoices/{id}/followups` | List drafts |
| GET | `/api/invoices/{id}/dispute-pack` | Download pack (`format=pdf\|md`) |
| GET | `/api/buyers` · `/api/buyers/{id}/profile` | Buyer reliability |
| GET | `/api/forecast?days=30\|60` | Cash-at-risk forecast |

## Project layout

```
backend/
  app/
    main.py              FastAPI app, CORS, startup
    api/routes.py        HTTP routes (thin)
    services.py          glue: upload, process, persistence, follow-ups, forecast, pack
    pipeline.py          extracted package → checks → score → due date → actions → graph
    schemas.py           Pydantic contracts (frozen; SCHEMA_VERSION)
    db/                  SQLModel tables, session, init_db()
    extraction/          classifier, text / fixture / claude extractors, fallback chain
    llm/                 thin Claude client + prompts (JSON only)
    matching/            normalisation, checks C01–C14, evidence graph
    rules/               config.yaml, due date, interest
    scoring/             score + tier, actions, buyer profile
    followups/           follow-up draft templates
    forecast/            cash-at-risk
    dispute/             evidence pack (Markdown + PDF)
    seed.py              synthetic payment history
    fmt.py               INR (₹2,40,000) and date formatting
  tests/                 pytest suite
samples/
  generate.py            synthetic package generator (reportlab)
  ground_truth.json      true values + injected defects (committed)
  out/                   generated PDFs (git-ignored, reproducible)
docs/
  api_contract.md        REST contract
  architecture.md        one-page architecture + diagram, results, limits
  demo_script.md         3-minute demo script with setup and recovery
  references.md          sources (legal, rates) + design-decision log
  bugs.md                UI run-through results + bug log (owner tags)
  progress.md            one line per finished task
frontend/                React + Vite + Tailwind: pages/, components/, lib/ (api client, formatting)
eval/                    run_eval.py + report.md (field accuracy, check precision/recall, due dates, timing)
```

## Testing

```powershell
cd backend; ..\.venv\Scripts\python -m pytest -q
```

The suite covers the rule functions (due date, interest, score), every check against all 28
ground-truth packages in `fixture` mode, the `text` extractor (exact on digital PDFs and
`uncertain`, never wrong, on scans), the LLM client offline, the full REST API, follow-ups, the
forecast, the dispute pack, and confidence gating.

```powershell
cd frontend; npm test; npm run lint                       # vitest unit/component tests + eslint
.\.venv\Scripts\python eval\run_eval.py                    # from the repo root: rewrites eval/report.md
```

`eval/run_eval.py` measures field accuracy, check precision/recall, due dates and processing time
in `text` and `fixture` mode (`--modes claude` needs an API key). A manual browser run-through of
all 28 packages is in `frontend/scripts/ui_runthrough.mjs` (see `docs/bugs.md`).

## Design principles

- **Deterministic first, LLM second.** Checks, scores, due dates and interest are plain Python. An
  LLM may fill extracted fields or rephrase text, but it never changes a status or a score.
- **Never silently trust a low-confidence field.** A field read below
  `extraction.uncertain_below` makes dependent checks `uncertain`. It is not used in calculations
  and is shown as "needs human check" / "[to be verified]".
- **Configurable law.** Legal and rate values live in `config.yaml` and are labelled *verify*.
- **Explainable output.** Each score lists its penalties, each due date gives its reasoning, and
  each interest figure shows its formula.

## Security and data handling

- **No secrets in git.** `.env` and `.env.*` are git-ignored, and only `.env.example` (with empty
  values) is committed. Pass `ANTHROPIC_API_KEY` through the environment.
- **Local data stays local.** The SQLite database and uploaded files live under `backend/data/`,
  which is git-ignored. Generated sample PDFs (`samples/out/`) are git-ignored as well.
- **No full document text in logs.** The LLM client logs only the status, model and request id.
- **Synthetic data only.** Sample companies, GSTINs and Udyam numbers are fictional. Don't
  commit real invoices or customer documents.
- If you find a secret in the history, rotate it first, then remove it from the history.

## Contributing workflow

- Work on a feature branch. Never push directly to `main`.
- Run the full test suite, then open a pull request into `main`.
- QA reviews the PR and posts a `VERDICT: APPROVE` or `VERDICT: REQUEST_CHANGES` comment.
- Only the repository owner merges.
- Each finished task ticks its box in `task.md` and adds one line to `docs/progress.md`.
- `backend/app/schemas.py` and `docs/api_contract.md` are frozen contracts. Breaking changes need
  owner sign-off and a `SCHEMA_VERSION` bump.

## Known limitations

- Accuracy is measured on **synthetic** documents. Real-world scans are messier.
- The `claude` extractor has been tested offline only, and its live accuracy is not measured yet.
- The deemed-acceptance rule and the RBI bank rate must be **verified** against current law before
  any real use.
- Buyer reliability uses only the supplier's own (seeded) history. It is not a credit rating.
- The product shows evidence gaps and statutory timelines. It does not predict whether a buyer
  will pay, and it does not send messages or file legal references.
