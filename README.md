# VyapaarIQ

**Upload an invoice package → build an Invoice Evidence Graph → detect what could block or weaken
payment → explain the risk → recommend the next action → draft follow-ups and a dispute-ready
evidence pack.**

VyapaarIQ is for **Indian MSME suppliers who sell on credit**. When a buyer pays late or disputes
an invoice, the supplier has to prove three things: the buyer **ordered** the goods, the goods were
**delivered**, and the buyer **accepted** them. That proof is usually scattered across PDFs, phone
photos and WhatsApp. The supplier often doesn't know which invoices are at risk until they are
already overdue.

VyapaarIQ reads every document behind an invoice (PO, invoice, delivery challan, e-way bill, GRN)
and cross-checks them with 14 deterministic checks. It shows the gaps on an evidence graph and
works out the MSMED Act due date and interest. It then tells the supplier what to fix first and
drafts the follow-ups and the evidence pack.

The scale of the problem: as of June 2026, the government's MSME Samadhaan portal had logged
**2,56,892 delayed-payment applications** from micro and small suppliers, with claims worth
**₹55,244.29 crore** (PIB, 26 Jun 2026; see [`docs/references.md`](docs/references.md) D-42).

> **Demo project.** All data is **synthetic** and every company is **fictional**. Risk scores and
> forecasts are *illustrative*, not a prediction of whether a buyer will pay. Legal values (45/15-day
> rules, bank rate, interest) are configurable and labelled *estimated / verify*. **Nothing here is
> legal advice.**

### Start here

| You want to… | Go to |
|---|---|
| Understand how everything works, with every term defined | **[`docs/tutorial.md`](docs/tutorial.md)** |
| Try it without installing anything | The hosted demo (password-protected; ask the owner for the link and password). See [`docs/deploy.md`](docs/deploy.md) |
| Run it on your laptop | [Quick start](#quick-start) (about 10 minutes) |
| Give the 3-minute demo | [`docs/demo_script.md`](docs/demo_script.md), run from the tag `v0.1.2-demo` |
| See the architecture on one page | [`docs/architecture.md`](docs/architecture.md) |
| Call the API | [`docs/api_contract.md`](docs/api_contract.md) (v1.0, frozen) |
| Check a legal value, a source or a design decision | [`docs/references.md`](docs/references.md) (sources R-1…R-7, decisions D-1…D-42) |
| See how well it works | [`eval/report.md`](eval/report.md) and [Quality](#quality) |
| Contribute | [Contributing workflow](#contributing-workflow) and [`CLAUDE.md`](CLAUDE.md) (the rules every change follows) |

---

## Contents

1. [Features](#features)
2. [The app, screen by screen](#the-app-screen-by-screen)
3. [How it works](#how-it-works)
4. [Status](#status)
5. [Requirements](#requirements)
6. [Quick start](#quick-start)
7. [Configuration](#configuration)
8. [Running a demo end to end](#running-a-demo-end-to-end)
9. [Verification checks (C01–C14)](#verification-checks-c01c14)
10. [Due date, interest and score](#due-date-interest-and-score)
11. [API overview](#api-overview)
12. [Hosted demo and releases](#hosted-demo-and-releases)
13. [Project layout](#project-layout)
14. [Testing](#testing)
15. [Quality](#quality)
16. [Design principles](#design-principles)
17. [Security and data handling](#security-and-data-handling)
18. [Contributing workflow](#contributing-workflow)
19. [Known limitations](#known-limitations)
20. [Documentation map](#documentation-map)

---

## Features

| Feature | What you get |
|---|---|
| Package upload | PDF / PNG / JPG files for one invoice: invoice, PO, delivery challan / LR, e-way bill, GRN / acceptance, contract. The type of each file is detected automatically, or you can set it. |
| Extraction | Structured fields per document. Each field carries `value`, `confidence` and `source_page`. Fields below the confidence threshold are marked "needs human check" and never used in a calculation. |
| 14 verification checks | Cross-document matching: PO reference, amounts and GST math, line items, buyer identity, delivery proof, quantities, receiving stamp, date order, e-way bill, GRN, payment terms, Udyam, duplicates. |
| Evidence graph | Nodes are the documents. Edges show the match status (`matched / mismatch / missing / uncertain`), and a click explains it. This is the main demo screen. |
| Readiness score | 0–100 with a Low / Medium / High risk tier. Every penalty is listed. |
| Ranked actions | What to fix first, the owner role (sales, supplier accounts, dispatch) and a due-by date. Overdue invoices say *"act now · payment overdue since …"*. |
| Due date and interest | Acceptance date (GRN, stamped challan, or deemed acceptance), the MSMED 45/15-day terms, and estimated s.16 compound interest with the formula shown. |
| Follow-up drafts | D−7, D−1, D+3, D+10 and D+25 drafts, friendly or firm, for email or WhatsApp. **Drafts only, never sent.** |
| Buyer reliability | Median days late, % paid late, % over 30 days late, trend, and a Reliable / Mixed / Slow label from the supplier's own history (seeded synthetic history in the demo). |
| Cash-at-risk forecast | 30 / 60-day view with buckets, a transparent formula and the excluded invoices listed. Opens as a table on phones. |
| Dispute evidence pack | PDF (with a Markdown fallback) in 9 sections: summary, invoice facts, document index, timeline, checks, due-date reasoning, interest estimate, missing evidence and the suggested next step (MSME ODR portal; verify). |

## The app, screen by screen

| Screen | What it shows |
|---|---|
| **Dashboard** | Open receivables, cash at risk in 30 and 60 days ("not expected by …"), expected in 30 days, the forecast chart, invoices by risk tier, the top 5 actions across all invoices, and the invoice list (cards on a phone). |
| **New package** | Drop in the files for one invoice. Each file's type is detected and can be changed. **Process package** opens the result. |
| **Invoice detail** | The header shows tiles for the amount, the estimated due date and its basis, readiness and tier, and the interest to date, plus the extractor used. *How the due date and interest were worked out* expands to show the reasoning and the formula. Below the header is the **evidence graph**, then five tabs: **Checks** (failing first; skipped ones grey), **Actions & score** (ranked actions and the penalty breakdown), **Documents** (every extracted field, amber when unsure), **Follow-ups** (generate drafts, switch tone or channel, copy) and **Dispute pack** (preview, download PDF or Markdown). |
| **Buyers** | Each buyer's reliability label, invoice count, median days late, % paid late, % over 30 days late and trend. A notice says the history is synthetic. |
| **How it works** | The whole flow on one page: five steps, the 14 checks, the MSMED due-date and interest rules, a card per tool, the PKG07 worked example and a glossary. |

**Hover to learn.** Every tool explains itself: hover (or focus, or tap) a navigation item, an invoice tab, a KPI tile or a
card's ⓘ to see what it does, its key rules and a *Learn more* link to the matching section of How it works. The
descriptions live in one file, `frontend/src/lib/tools.js`.

A banner on every page says: *synthetic data only · risk scores are illustrative · legal figures
are estimates, not legal advice*. A status chip shows whether the API is reachable, the extractor
mode and the demo date.

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

1. **Upload** creates a *package*. The files are stored and classified, first by first-page
   keywords, then by file name.
2. **Process** extracts each file. It then runs checks C01–C14 and computes the score, due date,
   interest, actions and graph, and stores everything. If one file fails, the others are still
   processed and kept. Each package logs one line with its ids, document count, extractor and time.
3. The **API** serves the results to the frontend. Follow-ups, the forecast and the dispute pack
   are built on demand from the stored analysis.

A step-by-step walk through one real example (PKG07: no GRN, score 70, due 13 Oct 2026, interest
₹452.05) is in [`docs/tutorial.md`](docs/tutorial.md#10-worked-example-pkg07-end-to-end).

## Status

| Area | State |
|---|---|
| Rules: due date, deemed acceptance, 45/15-day terms, s.16 interest | ✅ tested |
| Checks C01–C14, readiness score, ranked actions, evidence graph | ✅ tested against ground truth (28 packages) |
| Confidence gating (low-confidence values never used in calculations) | ✅ tested |
| Extraction: `text` (PyMuPDF + regex), `fixture`, `claude` (optional) | ✅ (`claude` path tested offline only; not used in the demo, D-35) |
| Synthetic generator: 28 packages / 133 PDFs, 5 phone-scan style | ✅ deterministic |
| REST API + SQLite: packages, invoices, graph, actions, buyers, forecast | ✅ tested; contract v1.0 frozen (D-40) |
| Seed history, follow-up drafts, forecast, dispute pack | ✅ tested |
| React frontend (React 19, React Router 7, Tailwind): all four screens, desktop and phone | ✅ vitest + scripted browser run-through of all 28 packages |
| Evaluation ([`eval/report.md`](eval/report.md)) | ✅ `text`: 0 confidently wrong fields, detection precision 100 % |
| Legal values (bank rate, MSMED s.2(b)/15/16, ITA 2025 s.37(2)(g), ODR) | ✅ researched 2026-11-24 (references L-1…L-4); final sign-off by the owner |
| Hosted demo (Render Free, password gate, HSTS) | ✅ live; public checks pass ([`docs/deploy.md`](docs/deploy.md)) |
| Releases | `v0.1-demo`, `v0.1.1-demo` and `v0.1.2-demo` (current demo build, redesigned UI) |

## Requirements

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ (the venv and the hosted image use 3.13) | Backend |
| Node.js | **22.12+** (or 24) | Frontend. Vitest 5 needs Node 22.12 or newer; `npm run dev` / `build` also work on Node 20, but the tests do not |
| Git | any recent | |
| Anthropic API key | optional | Only for `EXTRACTOR=claude`. API credit is billed separately from a Claude Pro plan. |

Python packages:

- [`backend/requirements-runtime.txt`](backend/requirements-runtime.txt): what the API needs.
  FastAPI, Uvicorn, SQLModel, Pydantic, PyMuPDF, reportlab, PyYAML, rapidfuzz, python-multipart
  and Pillow.
- [`backend/requirements.txt`](backend/requirements.txt): the development install. It adds the
  optional `anthropic` client, `pytest` and `httpx`.
- [`backend/constraints-runtime.txt`](backend/constraints-runtime.txt): pins the exact versions
  the tests run with. The hosted image uses it.

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

Open http://localhost:5173, go to **New package**, and drop in the PDFs from
`samples\out\PKG07\`. For the exact numbers in the demo script, start the API with
`$env:EXTRACTOR="fixture"; $env:VYAPAARIQ_TODAY="2026-11-23"` (see
[Running a demo](#running-a-demo-end-to-end)).

### macOS / Linux

Run the same steps with `python3 -m venv .venv` (Python 3.11+), and use `.venv/bin/pip`,
`.venv/bin/python` and `.venv/bin/uvicorn` instead of `.\.venv\Scripts\...`.

## Configuration

### Environment variables

Copy [`.env.example`](.env.example) to `.env` and set only what you need. Never commit `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `EXTRACTOR` | `text` | `claude` \| `text` \| `fixture`. Falls back automatically along `claude → text → fixture`. |
| `ANTHROPIC_API_KEY` | – | Needed only for `EXTRACTOR=claude`. `ANTHROPIC_AUTH_TOKEN` is also accepted in its place. |
| `LLM_MODEL` | `claude-opus-5-5` | Model id for the `claude` extractor. Check it against the current Anthropic docs. |
| `LLM_EFFORT` | `medium` | `low` \| `medium` \| `high`. |
| `VYAPAARIQ_DB` | `backend/data/vyapaariq.db` | SQLite file path. |
| `VYAPAARIQ_TODAY` | today | Pins "today" (`YYYY-MM-DD`) for reproducible demos. It affects due dates, interest, the forecast and past drafts. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed to call the API. |
| `GROUND_TRUTH` | `samples/ground_truth.json` | Ground-truth file used by the `fixture` extractor. |
| `VYAPAARIQ_LOG_LEVEL` | `INFO` | App log level (case-insensitive; an unknown name falls back to INFO with a warning). At `INFO`, each processed package logs one line: ids, document count, extractor and time in ms. Document text is never logged. |
| `VITE_API_BASE` | `http://localhost:8000` | Frontend build: base URL of the API. Use `/` when the API serves the UI itself (hosted demo). |

**Hosted-demo variables.** These are set in the image or on the host, and each is a no-op when
unset ([`docs/deploy.md`](docs/deploy.md)):

| Variable | Purpose |
|---|---|
| `DEMO_PASSWORD`, `DEMO_USER` (`demo`) | HTTP Basic auth on every path except `/api/health`. **Set only in the host's secret settings.** |
| `STATIC_DIR` | Serve the built UI (`frontend/dist`) from the API, same origin, with SPA fallback |
| `DEMO_BOOTSTRAP=1`, `DEMO_PRELOAD` (`PKG01,PKG20`), `SAMPLES_DIR` | On an empty DB: seed history and preload these sample packages |
| `PORT` | Port the container listens on (set by the host) |

### Extractor modes

| Mode | What it does | Needs |
|---|---|---|
| `text` (default) | PyMuPDF text layer plus regex heuristics. Scanned pages come back *uncertain*. | nothing |
| `claude` | Claude reads the text, or the PDF/image for scans, and returns validated JSON. | `ANTHROPIC_API_KEY`, optional `LLM_MODEL` |
| `fixture` | Reads `samples/ground_truth.json`, so the demo runs offline. It reads only the 28 sample packages. | nothing |

Anything produced by a fallback is flagged `fallback: true`, and the UI shows a **"demo
fallback"** badge for it.

### Rule values

Every tolerance, penalty, threshold and legal parameter lives in
[`backend/app/rules/config.yaml`](backend/app/rules/config.yaml). None of them are hard-coded.

| Key | Default | Meaning |
|---|---|---|
| `supplier.enterprise_class` | `small` | MSMED s.15/16 apply only to `micro` / `small`. |
| `msmed.max_terms_days` / `no_agreement_days` | 45 / 15 | s.15 limits. |
| `msmed.deemed_acceptance_offset_days` | 0 | Deemed acceptance = delivery date + N days. 0 follows MSMED s.2(b): the day of actual delivery, when there is no written objection within 15 days (checked against the Act text, L-2). |
| `rbi.bank_rate_pct` | 5.75 (as of 2026-10-07) | Interest uses 3 × this rate (17.25 %). Confirmed on RBI's 7 Oct 2026 MPC resolution (L-1); re-check whenever the RBI changes rates. |
| `legal_refs.buyer_deduction_rule` | s.37(2)(g), Income-tax Act 2025 | The buyer-side tax rule quoted in drafts (formerly s.43B(h)); text only (L-3). |
| `extraction.uncertain_below` | 0.60 | Fields read below this confidence are `uncertain` and never used in calculations. |
| `scoring.penalties` | blocker 25 (C10 = 30), warning 10, uncertain 5 | Score = 100 − Σ penalties. |
| `scoring.tiers` | Low ≥ 85, Medium 60–84, High < 60 | |
| `eway.threshold_inr` | 50,000 | C09 e-way bill requirement. |
| `buyer_profile.min_history` | 5 | Fewer paid invoices → "Insufficient history". |
| `followups.steps` | −7, −1, 3, 10, 25 | Days relative to the due date. |
| `actions.lead_days_before_due` | 7 | An action's due-by date is this many days before the payment due date (or today). |

## Running a demo end to end

**In the browser:** follow [`docs/demo_script.md`](docs/demo_script.md). It checks out
`v0.1.2-demo` into a separate folder, seeds the database, preloads two packages, and walks through
PKG07 in 3 minutes. It also covers recovery steps. A captioned backup video can be recorded with
`frontend/scripts/record_demo.mjs`.

**From the command line** (with the API running with `EXTRACTOR=fixture` and
`VYAPAARIQ_TODAY=2026-11-23` for reproducible numbers):

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

On Windows PowerShell, write `curl.exe` instead of `curl`.

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

Each check returns:

- a `status`: `pass / fail / missing / uncertain`,
- a `severity`: `blocker / warning / info`,
- a plain-English `detail`,
- the evidence it used.

A check that depends on a field read with low confidence returns `uncertain` rather than guessing.
An info check reporting `missing` because its input document is absent is shown as **skipped**.

| ID | Check | Fails when | Severity |
|---|---|---|---|
| C01 | Invoice ↔ PO reference | no PO ref, PO not in package, or numbers differ | blocker |
| C02 | Amount reconciliation | taxable > PO value + 1 %, or taxable + GST ≠ total (± ₹1) | blocker |
| C03 | Line items vs PO | qty / rate above PO beyond tolerance (> 10 % is a blocker) | warning / blocker |
| C04 | Party consistency | buyer name / GSTIN differ across documents (fuzzy name match ≥ 0.90) | blocker |
| C05 | Delivery proof exists | no challan / LR | blocker |
| C06 | Delivered ≥ invoiced qty | challan qty < invoice qty | blocker |
| C07 | Receiving evidence | no receiver stamp or signature on challan | warning |
| C08 | Date logic | challan > 7 days after invoice, or PO dated after invoice | warning |
| C09 | E-way bill | value above ₹50,000 and no / mismatched e-way bill | warning |
| C10 | GRN / acceptance | no GRN or written acceptance | blocker |
| C11 | Payment terms defined | no written terms (15-day rule applies) | warning |
| C12 | Terms ≤ 45 days | terms > 45 days for a micro/small supplier | warning |
| C13 | Supplier Udyam present | no Udyam number on supplier documents | info |
| C14 | Duplicate invoice | same invoice no. + buyer already on record | blocker |

## Due date, interest and score

- **Acceptance date** is the GRN date if there is one. Otherwise it is the received date on the
  delivery challan. Otherwise it is *deemed* acceptance: the delivery date, per MSMED s.2(b). That
  last case is configurable and labelled "deemed / estimated · verify".
- **Due date** is acceptance + min(written terms, 45) days, or acceptance + 15 days when there are
  no written terms. The 45-day cap and the 15-day default are MSMED rules for micro and small
  suppliers. For a `medium` supplier, written terms apply as written, and without written terms
  15 days is only an assumption (marked `uncertain`). The response always states which rule
  produced the date.
- **Interest** is an estimate of MSMED s.16 interest: compound with monthly rests, at 3 × the RBI
  bank rate, on the delay beyond the due date. Full 30-day months compound, and the remaining days
  accrue pro rata. The formula is returned with the number, and interest is not computed when the
  invoice total could not be read reliably.
- **Score** is 100 − Σ penalties, clamped to 0–100, with tiers from config. It is an illustrative
  readiness score, not a prediction of whether the buyer will pay.

## API overview

All paths start with `/api`. Request and response shapes, enums, error codes and example JSON are
in **[`docs/api_contract.md`](docs/api_contract.md)** (v1.0, frozen; changes need a PR, a QA verdict
and a schema-version bump).

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness, schema version, extractor mode, demo date, UI thresholds |
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

## Hosted demo and releases

- **Hosted demo (D-41).** A password-protected copy runs on Render's free plan, built from the
  `Dockerfile` and `render.yaml`. One container serves the API and the UI. It runs in `fixture`
  mode with the demo date pinned. Every start reloads the synthetic history plus PKG01 and PKG20,
  and nothing persists between restarts.
  - The first visit after 15 idle minutes takes 30–60 seconds.
  - Auto-deploy is off. After a merge, use **Manual Deploy → Deploy latest commit**.
  - Owner steps and post-deploy checks: [`docs/deploy.md`](docs/deploy.md).
- **Releases (tags).**
  - `v0.1-demo` (`c5ec290`): the first demo-verified build.
  - `v0.1.1-demo` (`283f137`): adds the evidence-graph click fix and the updated demo script.
  - `v0.1.2-demo`: the redesigned UI (D-43: sidebar, hover cards, How it works page) with the demo
    script re-checked on it. Tagged by the owner on the merge commit of the PR that updates the script.
    **Use this one for the demo.**
  - Release checks (tests, secret scan, dependency audit) are in [`docs/release.md`](docs/release.md).

## Project layout

```
backend/
  app/
    main.py              FastAPI app, CORS, logging, startup
    deploy.py            hosted demo only: password gate, same-origin UI, demo bootstrap (env-gated)
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
  tests/                 pytest suite (124 tests)
  requirements*.txt      runtime / development installs; constraints-runtime.txt pins versions
frontend/
  src/pages/             Dashboard, NewPackage, InvoiceDetail, Buyers (+ tests)
  src/components/        evidence graph, forecast chart, follow-ups, dispute pack, fields, UI kit
  src/lib/               API client, INR/date formatting, hooks
  scripts/               manual tools: ui_runthrough.mjs (all 28 packages), record_demo.mjs (backup video)
samples/
  generate.py            synthetic package generator (reportlab), deterministic
  ground_truth.json      true values + injected defects (committed)
  out/                   generated PDFs (git-ignored, reproducible)
eval/                    run_eval.py + report.md (field accuracy, check precision/recall, due dates, timing)
docs/                    see the documentation map below
Dockerfile, render.yaml  hosted demo image and Render blueprint
```

## Testing

```powershell
cd backend; ..\.venv\Scripts\python -m pytest -q          # 124 tests
cd frontend; npm test; npm run lint                       # 43 vitest tests + eslint (Node 22.12+)
.\.venv\Scripts\python eval\run_eval.py                    # from the repo root: rewrites eval/report.md
```

The backend suite covers:

- the rule functions (due date, interest, score),
- every check against all 28 ground-truth packages in `fixture` mode,
- the `text` extractor (exact on digital PDFs; `uncertain`, never wrong, on scans),
- the LLM client offline,
- the full REST API, follow-ups, the forecast and the dispute pack,
- confidence gating,
- the hosted-demo gate (password, HSTS, SPA fallback, bootstrap).

`eval/run_eval.py` measures field accuracy, check precision and recall, due dates and processing
time in `text` and `fixture` mode (`--modes claude` needs an API key). The manual browser
run-through (`frontend/scripts/ui_runthrough.mjs`) uploads all 28 packages through the UI. It
exits 1 on any mismatch or console error (see [`docs/bugs.md`](docs/bugs.md)).

## Quality

| Measure (`text` mode, 28 synthetic packages) | Result |
|---|---|
| Field extraction accuracy | 93.5 % |
| **Wrong but confident fields** | **0** |
| Defect detection precision / recall | 100 % / 88.5 % |
| Package verdicts | 24 / 28 correct, 4 abstained, **0 wrong** |
| Due dates | 27 / 28 |
| Median processing time | about 13 ms per package |

Every `text`-mode difference comes from a **scanned** document. Without OCR, a scan is marked
*uncertain* for a human check rather than guessed (D-36). `fixture` mode scores 100 % on every
measure. The full report, with failure cases, is in [`eval/report.md`](eval/report.md).

## Design principles

- **Deterministic first, LLM second.** Checks, scores, due dates and interest are plain Python. An
  LLM may fill extracted fields or rephrase text, but it never changes a status or a score.
- **Never silently trust a low-confidence field.** A field read below `extraction.uncertain_below`
  makes the checks that depend on it `uncertain`. It is not used in calculations, and it is shown
  as "needs human check" / "[to be verified]".
- **Configurable law.** Legal and rate values live in `config.yaml`, with their source and
  verification status in `docs/references.md`.
- **Explainable output.** Every score lists its penalties, every due date gives its reasoning,
  every interest figure shows its formula, and every evidence-graph link explains itself.
- **Drafts, not actions.** The app never sends a message or files a case. A person does.

## Security and data handling

- **No secrets in git.** `.env` and `.env.*` are git-ignored, and only `.env.example` (with empty
  values) is committed. Pass keys and the demo password through the environment or the host's
  secret settings. The release secret scan found nothing in any commit (`docs/release.md`).
- **Local data stays local.** The SQLite database and uploaded files live under `backend/data/`,
  which is git-ignored. Generated sample PDFs (`samples/out/`) are git-ignored as well.
- **No document text in logs.** Processing logs carry only ids, counts and timings. The LLM client
  logs only the status, model and request id.
- **Hosted demo.**
  - HTTP Basic auth on everything except the health check, with constant-time comparison.
  - The password is never logged.
  - HSTS is on every response, and `http://` redirects to `https://`.
  - WebSocket connections are refused.
  - The image runs as a non-root user, with pinned base images and Python versions.
- **Dependencies.** `npm audit` reports 0 vulnerabilities and `pip-audit` is clean (as of 2026-11-24).
- **Synthetic data only.** Sample companies, GSTINs and Udyam numbers are fictional. Don't commit
  or upload real invoices or customer documents.
- If you find a secret in the history, rotate it first, then remove it from the history.

## Contributing workflow

- Work on a feature branch from `main`. Never push directly to `main`, and don't stack PRs.
- Run the full test suite, then open a pull request into `main`.
- QA reviews the PR and posts `VERDICT: APPROVE` or `VERDICT: REQUEST_CHANGES`. **Once a verdict
  is posted, don't push to that PR.** Put follow-ups in a new PR, so the merged code is always the
  code that was reviewed.
- Only the repository owner merges and tags releases.
- Each finished task ticks its box in `task.md` and adds one line to `docs/progress.md`. Decisions
  and sources go in `docs/references.md`.
- `backend/app/schemas.py` and `docs/api_contract.md` are frozen contracts. Breaking changes need
  owner sign-off and a `SCHEMA_VERSION` bump.

## Known limitations

- Accuracy is measured on **synthetic** documents. Real-world scans are messier.
- The `claude` extractor (needed for scans) has been tested offline only. Its live accuracy is not
  measured, because the demo runs without an API key (D-35).
- Legal values were researched on 2026-11-24 (L-1…L-4), but some points are still open: the exact
  current ODR filing steps, whether a 2026 MSMED amendment has been enacted, and a direct read of
  the official ITA 2025 text. **Verify before any real use.**
- Buyer reliability uses only the supplier's own (seeded) history. It is not a credit rating.
- The hosted demo reads only the 28 sample packages (`fixture` mode), sleeps when idle, and resets
  its data on every restart.
- The product shows evidence gaps and statutory timelines. It does not predict whether a buyer
  will pay, and it does not send messages or file legal references.

## Documentation map

| Document | What it is |
|---|---|
| [`docs/tutorial.md`](docs/tutorial.md) | How everything works, with definitions, a worked example, a glossary and references |
| [`BUILD_SPEC.md`](BUILD_SPEC.md) · [`task.md`](task.md) | What to build · the plan, owners and status |
| [`CLAUDE.md`](CLAUDE.md) | Non-negotiable rules for every change |
| [`docs/architecture.md`](docs/architecture.md) | One-page architecture, diagram, measured results, limits |
| [`docs/api_contract.md`](docs/api_contract.md) | REST contract v1.0 (frozen) |
| [`docs/demo_script.md`](docs/demo_script.md) | 3-minute demo: setup, script, recovery, backup recording |
| [`docs/references.md`](docs/references.md) | Every external source and design decision (who, when, why), plus the verify list |
| [`docs/deploy.md`](docs/deploy.md) | Hosted demo on Render: steps, limits, checks |
| [`docs/release.md`](docs/release.md) | Release checks and tags |
| [`docs/bugs.md`](docs/bugs.md) | UI run-through results and the bug log |
| [`docs/progress.md`](docs/progress.md) | One line per finished task |
| [`eval/report.md`](eval/report.md) | Evaluation results and failure cases |
