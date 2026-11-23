# VyapaarIQ — Build Specification (5-day MVP)

> Read this file first. Every agent working on this repo must follow it.
> Companion file: `task.md` (day-by-day tasks, owners, acceptance criteria).

---

## 1. One-line goal

**Upload an invoice package → build an Invoice Evidence Graph → detect what could block or weaken payment → explain the risk → recommend the next action → generate follow-ups and a dispute-ready evidence pack.**

The demo must work end to end on 20–30 synthetic invoice packages with known ground truth, so accuracy can be *measured*, not just claimed.

## 2. Problem (why this exists)

Indian MSME suppliers deliver goods/services on credit; buyers pay late. Owners track invoices, POs, challans, acceptance and follow-ups manually (Excel, WhatsApp, memory). When a payment is disputed or delayed, the supplier often cannot quickly prove delivery and acceptance, and does not know *which* invoices are at risk until they are already overdue.

Legal context the product encodes (informational, configurable, not legal advice):

- MSMED Act 2006, s.15: buyer must pay a Micro/Small supplier within the agreed period, max **45 days** from acceptance/deemed acceptance; **15 days** if there is no written agreement.
- MSMED Act 2006, s.16: compound interest (monthly rests) at three times the RBI bank rate on delayed amounts.
- Income-tax Act s.43B(h) (from AY 2024-25): buyer's deduction for dues to Micro/Small suppliers beyond the s.15 limit is allowed only on actual payment. This gives suppliers leverage. *(Update: under the Income-tax Act, 2025, in force from 2026-04-01, this is s.37(2)(g); drafts cite the value in `config.yaml` `legal_refs`. See `docs/references.md` D-13 / R-4.)*
- Delayed-payment references: since Oct 2025 new references go through the **MSME ODR portal** (Samadhaan only for cases already pending). The dispute pack should be formatted for that route. **Verify current process before demo.**

Rule values live in `backend/app/rules/config.yaml`. Never hard-code them.

## 3. Scope

### In scope (MVP)
1. Upload a "package" (PDF/image files): invoice, PO, delivery challan / LR, e-way bill, GRN / buyer acceptance, optional contract/terms.
2. Extract structured fields from each document.
3. Cross-document matching and verification checks (Section 7).
4. Evidence Graph per invoice (nodes = documents, edges = match status).
5. Payment-readiness score (0–100) and risk tier with per-issue explanations.
6. Recommended next actions (ranked) with deadlines relative to due date.
7. Due-date computation from acceptance date + terms; MSMED 45-day flag.
8. Follow-up schedule + draft messages (email/WhatsApp text, *drafts only, never sent*).
9. Buyer reliability profile computed from the supplier's own invoice history (seeded demo history).
10. 30/60-day cash-at-risk forecast (transparent heuristic, not ML).
11. Dispute evidence pack export (Markdown → PDF) with timeline, document index, interest estimate.
12. Evaluation script that scores extraction + detection against ground truth.

### Out of scope (do NOT build)
Authentication/multi-tenancy, payments/collections, real WhatsApp/email sending, Tally/Zoho integration, invoice discounting/financing, mobile app, real buyer credit scoring, legal filing automation.

If time runs short, cut in this order: forecast → buyer profile UI → PDF export (keep Markdown) → follow-up scheduling UI (keep drafts).

## 4. Architecture

```
frontend (React + Vite + Tailwind)
        │ REST/JSON
backend (FastAPI, Python 3.11+)
  ├─ api/            routes
  ├─ extraction/     PDF text → (optional) vision LLM → validated JSON
  ├─ matching/       cross-document checks, evidence graph builder
  ├─ rules/          MSMED/GST/e-way config + due-date + interest
  ├─ scoring/        readiness score, risk tier, actions
  ├─ forecast/       cash-at-risk
  ├─ dispute/        evidence pack generator
  ├─ llm/            thin Claude client + prompts + JSON validation
  └─ db/             SQLite via SQLModel/SQLAlchemy
samples/             synthetic package generator + ground_truth.json
eval/                evaluation script + report
```

Design principles:
- **Deterministic first, LLM second.** Matching, scoring, due dates, interest are plain Python. The LLM is used for (a) extracting fields from messy docs, (b) writing human-readable explanations and draft messages. A wrong LLM sentence must never change a score.
- **Extractor interface with three modes** via `EXTRACTOR` env var: `claude` (vision/text API), `text` (PyMuPDF text + regex heuristics, for digital PDFs), `fixture` (reads `ground_truth.json`; guarantees the demo cannot fail offline). Default for demo recording: `claude` with `fixture` as fallback.
- Every extracted field carries `value`, `confidence` (0–1) and `source_page`. Low-confidence fields surface as "needs human check", never silently trusted.
- SQLite file DB. No Supabase, no Docker required.

### Cost / access note
Claude Pro (and Claude Code usage on it) and the Claude **API** are billed separately. The app's `claude` extractor needs `ANTHROPIC_API_KEY` with API credit. Verify model name in current docs and set via `LLM_MODEL` env var (do not hard-code). If no key, use `EXTRACTOR=text` or `fixture` and say so honestly in the demo.

## 5. Data model (SQLite)

```
supplier(id, name, gstin, udyam_no, enterprise_class)         -- one seeded row
buyer(id, name, gstin, aliases_json)
package(id, supplier_id, buyer_id, created_at, status)
document(id, package_id, doc_type, filename, path, extracted_json, extraction_conf, page_count)
    doc_type ∈ {invoice, po, challan, eway, grn, contract, other}
invoice(id, package_id, invoice_no, invoice_date, amount_total, amount_taxable,
        gst_amount, payment_terms_days, due_date, status, readiness_score, risk_tier)
check_result(id, invoice_id, check_id, status, severity, detail_json)
    status ∈ {pass, fail, missing, uncertain}
action(id, invoice_id, priority, title, rationale, due_by, owner_role, status)
followup(id, invoice_id, step, send_on, channel, draft_text, status)
payment_event(id, invoice_id, paid_on, amount)               -- history + seeded data
```

Seed data: `seed.py` creates 1 supplier, 6 buyers, and ~60 historical invoices with payment dates (some on time, some 20–90 days late) so buyer reliability is meaningful. State clearly in the UI that history is **synthetic demo data**.

## 6. Extraction schema (per document type)

Use Pydantic models; reject and retry once on validation failure.

Common: `doc_type, doc_no, doc_date, supplier_name, supplier_gstin, buyer_name, buyer_gstin, po_reference, page_count`

- **invoice**: `invoice_no, invoice_date, line_items[{desc, hsn, qty, unit, rate, amount}], taxable_value, cgst, sgst, igst, total, payment_terms_text, payment_terms_days, due_date_text, irn, bank_details_present`
- **po**: `po_no, po_date, line_items[...], po_total, delivery_date, payment_terms_text, payment_terms_days`
- **challan**: `challan_no, challan_date, invoice_reference, po_reference, line_items[{desc, qty}], vehicle_no, received_by_name, received_stamp_present, received_signature_present, received_date`
- **eway**: `eway_no, generated_date, invoice_reference, value, vehicle_no, valid_until`
- **grn**: `grn_no, grn_date, po_reference, invoice_reference, line_items[{desc, qty_received, qty_accepted}], accepted_by, remarks`
- **contract**: `payment_terms_text, payment_terms_days, deemed_acceptance_clause_present, interest_clause_text`

Extraction prompt rules (put in `llm/prompts.py`):
- Return **only JSON** matching the schema; unknown → `null`, never guess.
- Add `confidence` per field.
- Dates ISO `YYYY-MM-DD`. Amounts as numbers in INR, no symbols.
- Quote the exact source text for payment terms in `payment_terms_text`.

## 7. Verification checks (the core of the product)

Each check returns `{check_id, status, severity, detail, evidence_refs}`. Severity: `blocker` / `warning` / `info`.

| ID | Check | Fail condition | Severity |
|----|-------|----------------|----------|
| C01 | Invoice ↔ PO reference | invoice has no PO ref, or PO not in package, or numbers differ | blocker |
| C02 | Amount reconciliation | invoice taxable value > PO value (+tolerance 1%); or taxable+GST ≠ total (±₹1) | blocker |
| C03 | Line items vs PO | item qty or rate differs from PO beyond tolerance | warning/blocker |
| C04 | Party consistency | buyer name/GSTIN differs across docs (fuzzy match ≥ 0.9 after normalisation) | blocker |
| C05 | Delivery proof exists | no challan/LR in package | blocker |
| C06 | Delivered qty ≥ invoiced qty | challan qty < invoice qty | blocker |
| C07 | Receiving evidence | challan lacks receiver stamp/signature | warning |
| C08 | Date logic | challan date after invoice date by > N days, or PO date after invoice date | warning |
| C09 | E-way bill | goods value above configured threshold and no e-way bill / mismatched invoice ref | warning |
| C10 | GRN / acceptance | no GRN or written acceptance | blocker (this is the "acceptance missing" killer case) |
| C11 | Payment terms defined | no written terms found | warning (triggers 15-day rule note) |
| C12 | Terms ≤ 45 days | terms > 45 days for Micro/Small supplier | warning (flag as potentially non-compliant; do not assert illegality) |
| C13 | Supplier Udyam present | no Udyam number on supplier docs | info (MSMED protections depend on registration) |
| C14 | Duplicate invoice | same invoice_no + buyer already in DB | blocker |

Tolerances and thresholds come from `rules/config.yaml`.

### Due-date logic
`acceptance_date` = GRN date if present, else challan received date, else **deemed acceptance** = delivery date + 15 days (configurable, label as "deemed", show reasoning). `due_date` = acceptance_date + min(terms_days, 45) when a written agreement exists; if no written terms, `acceptance_date + 15`. Always show which rule produced the date. **Verify the deemed-acceptance rule against the Act text before the demo and keep the label "estimated".**

### Interest estimate
Compound monthly at 3 × configured RBI bank rate on delay beyond due date. Show as "estimated statutory interest" with the formula visible. Not legal advice.

### Readiness score
`score = 100 − Σ penalties`, clamp 0–100. Penalties from config: blocker 25 (C10 = 30), warning 10, uncertain 5. Tiers: ≥85 Low, 60–84 Medium, <60 High. The score is explainable: the UI lists each penalty. **Illustrative, not a buyer payment prediction.**

### Actions
Rule-generated, ranked by severity then deadline. Template per failed check, e.g. C10 → *"Request GRN/acceptance acknowledgement from buyer's receiving department before {due_date − 7d}"*. The LLM may rephrase rationale text only.

## 8. Buyer reliability profile
From `payment_event` history per buyer: median days-late, % paid late, % paid > 30 days late, trend (last 3 vs previous). Output a label (Reliable / Mixed / Slow) with the numbers shown. Minimum 5 historical invoices, else "Insufficient history".

## 9. Cash-at-risk forecast
For open invoices: expected payment date = due_date + buyer median days-late (0 if insufficient history). Bucket into next 30 / 60 days. "At risk" = amount of invoices with tier High, or expected date beyond the window. Present as a simple bar chart + table with the formula in a tooltip.

## 10. Follow-up schedule
Default cadence relative to due date: D−7 (courtesy + request missing doc), D−1, D+3, D+10 (cite 45-day rule, politely), D+25 (escalation draft). Tone variants: friendly / firm. Drafts include invoice no., amount, due date, and attach-list. Status stays `draft`.

## 11. Dispute evidence pack
Markdown template → PDF (use WeasyPrint or reportlab; fall back to Markdown if PDF fails). Sections: cover summary; invoice facts; document index with extracted keys; timeline (PO → delivery → acceptance → due → today); checks table; computed due date and reasoning; estimated interest; list of missing evidence; suggested next step (ODR portal route, verify). Footer: "Generated assistance, not legal advice."

## 12. API (FastAPI)

```
POST /api/packages                      multipart: files[] + buyer_name?  → package_id
POST /api/packages/{id}/process         run extraction → match → score
GET  /api/packages/{id}                 package + docs + extraction status
GET  /api/invoices                      list with filters (tier, buyer, status)
GET  /api/invoices/{id}                 invoice + checks + graph + actions + followups
GET  /api/invoices/{id}/graph           {nodes:[], edges:[]}
POST /api/invoices/{id}/followups/generate?tone=friendly|firm
GET  /api/invoices/{id}/dispute-pack    returns PDF/MD
GET  /api/buyers/{id}/profile
GET  /api/forecast?days=30|60
POST /api/eval/run                      dev only
GET  /api/health
```

Graph JSON:
```json
{"nodes":[{"id":"inv","type":"invoice","label":"INV-1042 ₹2,40,000","status":"ok"},
          {"id":"grn","type":"grn","label":"GRN","status":"missing"}],
 "edges":[{"from":"inv","to":"po","status":"matched","confidence":0.97,"note":"PO-778 matches"}]}
```

## 13. Frontend

Pages (keep to four):
1. **Dashboard** — total open receivables, cash at risk (30/60), invoices by tier, top 5 actions due.
2. **New package** — drag-and-drop upload, per-file doc-type detection, "Process" button with progress.
3. **Invoice detail** (the demo screen) — header (amount, buyer, due date + rule), **Evidence Graph**, checks list with severity chips and explanations, ranked actions, follow-up drafts tab, "Export dispute pack".
4. **Buyers** — reliability table with the numbers.

UI rules: show confidence on extracted fields; amber "needs human check" for low confidence; always label risk as illustrative; Indian number formatting (₹2,40,000); responsive but desktop-first. Render the graph with simple SVG or React Flow, whichever is faster to get right.

## 14. Synthetic data generator (`samples/`)

Script generates 25–30 packages as PDFs (reportlab) with a `ground_truth.json` recording true field values and injected defects. Defect mix (each ≥2 times): missing GRN, missing challan, qty short on challan, invoice > PO value, buyer name/GSTIN mismatch, missing PO reference, terms > 45 days, no stamp on challan, duplicate invoice, wrong GST math, clean package (≥5). Vary layouts/fonts a little; make 4–5 look like phone-scan images (rotate, blur, noise). Use fictional companies only.

## 15. Evaluation (`eval/run_eval.py`)

Report to `eval/report.md`:
- Field extraction accuracy per doc type (exact match for IDs/dates/amounts).
- Cross-document match accuracy (C01, C04 precision/recall).
- Defect detection precision/recall per check ID, and overall "package correctly classified blocker vs clean".
- Due-date correctness vs ground truth.
- Median processing time per package.
Honest numbers only; include failure cases.

## 16. Repo layout

```
vyapaariq/
  BUILD_SPEC.md  task.md  CLAUDE.md  README.md
  backend/app/{api,extraction,matching,rules,scoring,forecast,dispute,llm,db}/
  backend/tests/
  frontend/src/{pages,components,lib}/
  samples/{generate.py,out/,ground_truth.json}
  eval/{run_eval.py,report.md}
  docs/{demo_script.md,architecture.md}
```

## 17. Multi-agent working rules (Agent Bridge)

I have not inspected the Agent Bridge repo; follow its README for exact commands. Working rules regardless:

| Agent | Owns (only edit these) | Never touch |
|-------|------------------------|-------------|
| **A0 Architect** | `BUILD_SPEC.md`, `task.md`, `CLAUDE.md`, `backend/app/db`, `backend/app/schemas.py`, integration, final review, merges | — |
| **A1 Document intelligence** | `backend/app/extraction`, `backend/app/llm`, `samples/` | frontend, scoring |
| **A2 Backend & risk** | `backend/app/{api,matching,rules,scoring,forecast,dispute}`, `backend/tests` | frontend, extraction internals |
| **A3 Frontend & QA** | `frontend/`, `eval/`, `docs/demo_script.md` | backend internals |

- `backend/app/schemas.py` (Pydantic contracts) and `docs/api_contract.md` are written by A0 on **Day 1 morning** and frozen; changes go through A0.
- One git branch per agent (`a1-extraction`, …); A0 merges at the end of each day. Commit small, commit often.
- Agents message each other only for: contract changes, blockers, handoffs ("extraction endpoint ready, schema vX"). Keep messages short.
- If two agents need the same file, stop and ask A0.
- Every task ends with: run tests, update `task.md` checkbox, one-line note in `docs/progress.md`.

## 18. Definition of done (demo-ready)

- [ ] Upload a fresh package → graph + checks + score + actions appear in < 60 s.
- [ ] Seeded "GRN missing" package shows risk Medium/High with the right action and draft follow-up.
- [ ] Dispute pack exports for at least one invoice.
- [ ] Eval report exists with real numbers on ≥ 25 packages.
- [ ] Runs from a clean clone with `README.md` steps (≤ 5 commands) and `EXTRACTOR=fixture` fallback.
- [ ] 3-minute demo script rehearsed twice.

## 19. Known risks and honest limitations

- Real-world documents are messier than synthetic ones; say so. Report accuracy on synthetic data as such.
- Legal/rate parameters can change; they are configurable and labelled "verify".
- Buyer reliability uses the supplier's own history only; seeded history is synthetic.
- The product does not predict whether a buyer *will* pay; it shows evidence gaps and statutory timelines.
- Documents contain personal/business data: process locally, do not log full extracted text, add a "demo data only" banner.
