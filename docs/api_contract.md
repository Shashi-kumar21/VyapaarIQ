# VyapaarIQ API contract

> **Status:** v1.0, written from the running backend (task T1.2). It needs sign-off from A0 / the owner before it is frozen.
> **Schema:** `backend/app/schemas.py` `SCHEMA_VERSION = "1.1"` (returned by `/api/health`).
> **Examples:** captured from the real API with `EXTRACTOR=fixture`, `VYAPAARIQ_TODAY=2026-11-23`, seeded history, and package `PKG07` (GRN missing). Long lists are trimmed with `…`.
> Every risk, score, interest and forecast value is *illustrative / estimated / not legal advice*. The UI must keep those labels visible.

## Conventions

| Topic | Rule |
|---|---|
| Base URL | `http://localhost:8000` in development. Every path starts with `/api`. The frontend reads the base from `VITE_API_BASE`. |
| Format | JSON (UTF-8) unless stated otherwise. Dates are ISO `YYYY-MM-DD`, timestamps ISO 8601 in UTC. |
| Amounts | Numbers in INR with no symbol (`22921.5`). The UI formats them with Indian grouping (`₹22,922`). |
| Unknown values | `null`. A value read below `extraction.uncertain_below` (0.60) is **never** used in calculations. Summary fields come back `null`, and the field stays visible with its `confidence` in `documents[].fields` for a human check. |
| Extracted field | `{"value": …, "confidence": 0.0–1.0, "source_page": int\|null}` |
| Demo clock | `VYAPAARIQ_TODAY=YYYY-MM-DD` pins "today" (due dates, interest, forecast, past drafts). |
| Errors | `{"detail": "<clear message>"}`. Status codes: `400` bad input, `404` not found, `409` not processed or no due date, `422` validation or processing failure. A FastAPI query-validation `422` returns `detail` as a **list** of `{loc, msg, type}`. |
| Auth | None (out of scope, local demo). |
| CORS | Allowed origins come from the `CORS_ORIGINS` env var (comma-separated). The default is `http://localhost:5173,http://127.0.0.1:5173` (the Vite dev server). |

## Endpoint index

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness, schema version, extractor mode, demo date |
| POST | `/api/packages` | Upload files → package |
| POST | `/api/packages/{id}/process` | Extract → checks → score → store |
| GET | `/api/packages/{id}` | Package, documents and extracted fields |
| GET | `/api/invoices` | Invoice list with filters |
| GET | `/api/invoices/{id}` | Invoice + full analysis + documents |
| GET | `/api/invoices/{id}/graph` | Evidence graph only |
| GET | `/api/actions?limit=5` | Top open actions across invoices (dashboard) |
| POST | `/api/invoices/{id}/followups/generate` | (Re)generate follow-up drafts |
| GET | `/api/invoices/{id}/followups` | List drafts |
| GET | `/api/invoices/{id}/dispute-pack` | Download evidence pack (PDF or Markdown) |
| GET | `/api/buyers` | Buyers with reliability profile |
| GET | `/api/buyers/{id}/profile` | One buyer's profile |
| GET | `/api/forecast?days=30\|60` | Cash-at-risk forecast |

`POST /api/eval/run` from BUILD_SPEC §12 is **not implemented yet** (dev only, planned with T5.1).

---

## GET /api/health

```json
{"status": "ok", "schema_version": "1.1", "extractor": "fixture", "today": "2026-11-23", "uncertain_below": 0.6, "min_history": 5}
```

`uncertain_below` is `extraction.uncertain_below` from `config.yaml`. The UI uses it for the amber "needs human check" state, so the threshold is never hard-coded in the frontend. `min_history` is `buyer_profile.min_history`, the number of paid invoices a buyer needs before it gets a reliability label (the Buyers page shows it). (Both are additive keys, not breaking changes.)

## POST /api/packages

`multipart/form-data`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `files` | file, repeated | yes | `.pdf`, `.png`, `.jpg`, `.jpeg`. Max 15 MB each, not empty. |
| `buyer_name` | string | no | Used only when the buyer cannot be read confidently from the invoice. |
| `doc_types` | string (JSON list) | no | Same order as `files`, at most one entry per file. Each item is a `doc_type` or `null` (auto-detect), e.g. `["invoice", null, "grn"]`. Overrides auto-detection (`doc_type_method: "user"`). Anything else (not a list, too long, unknown type) is a `400`. |

`201 Created` returns the same shape as `GET /api/packages/{id}`, before processing:

```json
{
  "id": 1, "status": "uploaded", "error": null,
  "created_at": "2026-11-23T11:23:21.711196+00:00", "invoice_id": null,
  "documents": [
    {"id": 1, "filename": "PKG07_challan.pdf", "doc_type": "challan", "doc_type_method": "keywords",
     "extractor": null, "fallback": false, "extraction_conf": null, "page_count": null,
     "error": null, "fields": null},
    …
  ]
}
```

- `doc_type` ∈ `invoice | po | challan | eway | grn | contract | other`.
- `doc_type_method` ∈ `keywords | filename | user | none`. First-page keywords beat the filename, and `user` means it came from `doc_types`. There is no LLM classification step yet.
- An unreadable file is kept with `doc_type: "other"`, `doc_type_method: "none"` and a non-null `error`.
- Errors: `400` (`No files uploaded.`, `Unsupported file type: a.txt. Use PDF, PNG or JPG.`, `<name> is empty.`, `<name> is larger than 15 MB.`, `doc_types must be a JSON list with at most one entry per file; each entry is null or one of [...]`).

## POST /api/packages/{id}/process

Runs synchronously (no request body). It is safe to call again: the same invoice row is updated in place.

```json
{"package_id": 1, "invoice_id": 61, "status": "done", "processing_ms": 44}
```

- `404` `Package not found.`
- `422` `No invoice found in the package.` or `Analysis failed for this package.` The package `status` becomes `failed` with `error` set.
- A file that fails extraction does **not** fail the package. That document gets an `error`, and every other result is kept.

## GET /api/packages/{id}

Package `status` ∈ `uploaded | processing | done | failed`. After processing, each document carries its extracted `fields`:

```json
{
  "id": 1, "status": "done", "error": null, "created_at": "2026-11-23T11:23:21.711196+00:00", "invoice_id": 61,
  "documents": [
    {"id": 1, "filename": "PKG07_challan.pdf", "doc_type": "challan", "doc_type_method": "keywords",
     "extractor": "fixture", "fallback": false, "extraction_conf": 1.0, "page_count": 1, "error": null,
     "fields": {
       "doc_type": "challan", "filename": "PKG07_challan.pdf", "page_count": 1, "extractor": "fixture", "fallback": false,
       "doc_no": {"value": "DC/26-27/0307", "confidence": 1.0, "source_page": 1},
       "challan_date": {"value": "2026-09-11", "confidence": 1.0, "source_page": 1},
       "received_stamp_present": {"value": true, "confidence": 1.0, "source_page": 1},
       "received_date": {"value": "2026-09-13", "confidence": 1.0, "source_page": 1},
       "line_items": {"value": [{"desc": "SS Hex Bolt M12x50", "qty": 50.0, "hsn": null, "unit": null, "rate": null,
                                 "amount": null, "qty_received": null, "qty_accepted": null}, …],
                      "confidence": 1.0, "source_page": 1},
       …
     }}
  ]
}
```

- `fields` keys per `doc_type` follow `schemas.py` (§6). The common keys are `doc_no, doc_date, supplier_name, supplier_gstin, supplier_udyam, buyer_name, buyer_gstin, po_reference`.
- `extractor` ∈ `claude | text | fixture | none`. When `fallback: true`, the UI shows a **"demo fallback"** badge.
- `extraction_conf` is the mean confidence of the fields that were found. A field with `confidence < 0.60` must be shown in **amber, "needs human check"**.

## GET /api/invoices

Query parameters (all optional): `tier` (`Low | Medium | High`), `buyer_id` (int), `status` (`open | paid | disputed`), `include_history` (bool, default `false`; `true` also returns seeded synthetic history). The list is sorted newest first.

```json
[
  {"id": 61, "package_id": 1, "invoice_no": "SPC/26-27/0107", "invoice_date": "2026-09-10",
   "buyer_id": 1, "buyer_name": "Kaveri Auto Assemblies Pvt Ltd", "amount_total": 22921.5,
   "due_date": "2026-10-13", "status": "open", "readiness_score": 70, "risk_tier": "Medium",
   "synthetic": false}
]
```

`amount_total` and `invoice_date` are `null` when they could not be read confidently. `buyer_id` is resolved from a confidently read buyer GSTIN or name, otherwise from the `buyer_name` given at upload. It is `null` when neither is available. A buyer is never created from an unreadable name.

## GET /api/invoices/{id}

This is the invoice summary (same keys as the list), plus `processing_ms`, `documents` (same shape as in the package view) and `analysis` (`schemas.Analysis`):

```json
{
  "id": 61, "invoice_no": "SPC/26-27/0107", "amount_total": 22921.5, "due_date": "2026-10-13",
  "readiness_score": 70, "risk_tier": "Medium", "processing_ms": 44, "documents": [ … ],
  "analysis": {
    "invoice_no": "SPC/26-27/0107", "buyer_name": "Kaveri Auto Assemblies Pvt Ltd", "amount_total": 22921.5,
    "checks": [
      {"check_id": "C01", "name": "Invoice ↔ PO reference", "status": "pass", "severity": "blocker",
       "detail": "Invoice PO reference KAA/PO/2627/1142 matches the PO.", "explanation": null,
       "evidence_refs": ["inv", "po"], "facts": {"po_no": "KAA/PO/2627/1142"}},
      … 14 checks, C01–C14 …
    ],
    "score": {"score": 70, "tier": "Medium",
              "penalties": [{"check_id": "C10", "status": "missing", "severity": "blocker", "points": 30}],
              "note": "Illustrative readiness score, not a prediction of buyer payment."},
    "due": {"acceptance_date": "2026-09-13", "acceptance_basis": "challan_received", "terms_days_applied": 30,
            "terms_basis": "written_terms", "due_date": "2026-10-13",
            "reasoning": "No GRN; acceptance 2026-09-13 taken from the received date on the delivery challan. Written terms of 30 days applied. Due date 2026-10-13 (estimated).",
            "estimated": true, "uncertain": false, "msmed_applies": true},
    "interest": {"principal": 22921.5, "due_date": "2026-10-13", "as_of": "2026-11-23", "days_late": 41,
                 "annual_rate_pct": 17.25, "interest": 452.05, "computable": true,
                 "formula": "P x (1 + 17.25%/12)^1 x (1 + 17.25%/12 x 11/30) - P; rate = 3 x RBI bank rate 5.75%",
                 "note": "Estimated statutory interest (MSMED s.16). Not legal advice; verify the bank rate."},
    "actions": [
      {"priority": 1, "check_id": "C10",
       "title": "Request GRN / acceptance acknowledgement from the buyer's receiving department before 2026-11-23",
       "rationale": "Acceptance starts the MSMED payment clock; …", "due_by": "2026-11-23",
       "owner_role": "sales", "status": "open"}
    ],
    "graph": { … same as /graph … },
    "extractor_used": "fixture", "fallback_used": false
  }
}
```

Enumerations:

| Field | Values |
|---|---|
| `checks[].status` | `pass \| fail \| missing \| uncertain` |
| `checks[].severity` | `blocker \| warning \| info` |
| `checks[].explanation` | optional LLM rephrasing; **never** changes status or score |
| `score.tier` | `Low` (≥85) \| `Medium` (60–84) \| `High` (<60); thresholds come from config |
| `due.acceptance_basis` | `grn \| challan_received \| deemed \| unknown` |
| `due.terms_basis` | `written_terms \| written_terms_capped \| no_written_terms \| written_terms_unreadable \| unknown` |
| `interest.computable` | `false`, with the reason in `formula`, when there is no due date, the supplier is not micro/small, the total was not read reliably, or the total is negative |
| `actions[].owner_role` | `supplier_accounts \| sales \| dispatch` |

The `analysis` object is `null` if the invoice has not been processed.

## GET /api/invoices/{id}/graph

```json
{
  "nodes": [
    {"id": "inv", "type": "invoice", "label": "SPC/26-27/0107 ₹22,922", "status": "ok", "doc_no": "SPC/26-27/0107"},
    {"id": "po", "type": "po", "label": "Purchase order KAA/PO/2627/1142", "status": "ok", "doc_no": "KAA/PO/2627/1142"},
    {"id": "challan", "type": "challan", "label": "Delivery challan DC/26-27/0307", "status": "ok", "doc_no": "DC/26-27/0307"},
    {"id": "grn", "type": "grn", "label": "GRN / acceptance", "status": "missing", "doc_no": null}
  ],
  "edges": [
    {"from": "inv", "to": "po", "status": "matched", "confidence": 1.0,
     "note": "Invoice PO reference KAA/PO/2627/1142 matches the PO.", "check_ids": ["C01", "C02", "C03"]},
    {"from": "inv", "to": "challan", "status": "matched", "confidence": 1.0,
     "note": "Delivery challan present.", "check_ids": ["C05", "C06", "C07", "C08"]},
    {"from": "inv", "to": "grn", "status": "missing", "confidence": 0.0,
     "note": "No GRN or written acceptance from the buyer. Acceptance can only be deemed, which weakens the payment claim.",
     "check_ids": ["C10"]}
  ]
}
```

- Node `id` ∈ `inv | po | challan | eway | grn | contract`. `eway` appears only when an e-way bill is required or present, and `contract` only when a contract is present.
- `nodes[].status` ∈ `ok | missing | mismatch | uncertain`. `edges[].status` ∈ `matched | mismatch | missing | uncertain`.
- An amount or document number read with low confidence is shown as `? (verify)` (e.g. `"SPC/26-27/0101 ₹? (verify)"`, `"Purchase order No. ? (verify)"`). Any such node (invoice or document) becomes `uncertain` unless it is already `mismatch`, and its `doc_no` is `null`. The edge keeps the status its checks gave it.
- `409` `Invoice has not been processed yet.`

## GET /api/actions

The dashboard's "top actions due". Query parameter: `limit` (1–50, default 5; out of range returns `422`). It covers open actions on open, non-synthetic invoices. They are ranked the same way as within one invoice: severity first (blocker, then warning, then info; an `uncertain` check ranks half a step lower), then `due_by` (earliest first; none last).

```json
[
  {"invoice_id": 61, "invoice_no": "SPC/26-27/0107", "buyer_name": "Kaveri Auto Assemblies Pvt Ltd",
   "risk_tier": "Medium", "check_id": "C10", "severity": "blocker", "check_status": "missing",
   "title": "Request GRN / acceptance acknowledgement from the buyer's receiving department before 2026-11-23",
   "rationale": "Acceptance starts the MSMED payment clock; …", "due_by": "2026-11-23",
   "owner_role": "sales", "priority_in_invoice": 1}
]
```

## POST /api/invoices/{id}/followups/generate

Query parameters: `tone` = `friendly` (default) | `firm`; `channel` = `email` (default) | `whatsapp`. This replaces any existing drafts for that invoice with the same `tone` and `channel`. **Nothing is ever sent.**

```json
{
  "invoice_id": 61, "note": "Drafts only. Nothing is sent.",
  "followups": [
    {"id": 1, "invoice_id": 61, "step": -7, "step_label": "D-7", "send_on": "2026-10-06", "past": true,
     "channel": "email", "tone": "friendly", "status": "draft",
     "draft_text": "[DRAFT - not sent. Review before sending.]\n[Scheduled send date 06 Oct 2026 has passed; kept for reference. Use the latest step instead.]\n\nSubject: Upcoming payment: invoice SPC/26-27/0107 due 13 Oct 2026 (estimated)\n\nDear Kaveri Auto Assemblies Pvt Ltd Accounts Team,\n\n…"},
    … steps D-1, D+3, D+10, D+25 (from config `followups.steps`) …
  ]
}
```

- The bracketed lines at the top of `draft_text` are reviewer notes, not part of the message:
  - `[DRAFT …]` always.
  - `[VERIFY: …]` when the due date rests on deemed acceptance or an unreadable input, or when the amount is unverified. In that case the body says `[amount to be verified]`.
  - `[Scheduled send date … has passed …]` when `past` is `true`.
- `past` is computed against the demo clock each time the list is read.
- Errors: `404` invoice not found. `409` `Invoice has not been processed yet.` or `No due date could be determined for this invoice; resolve acceptance and payment terms first.` `422` if `tone` or `channel` is invalid.

## GET /api/invoices/{id}/followups

Optional filters: `tone`, `channel`. Returns a list of draft objects (same shape as above), ordered by tone, channel, step.

## GET /api/invoices/{id}/dispute-pack

Query parameter: `format` = `pdf` (default) | `md`. The response is a file download, not JSON:

| Header | PDF | Markdown |
|---|---|---|
| `content-type` | `application/pdf` | `text/markdown; charset=utf-8` |
| `content-disposition` | `attachment; filename="evidence-pack-SPC-26-27-0107.pdf"` | `… .md` |
| `x-pack-format` | `pdf` | `md`, or `md-fallback` when the PDF render failed |

Sections: Summary, Invoice facts, Document index, Timeline, Verification checks, Due date and reasoning, Estimated statutory interest, Missing or weak evidence, Suggested next step. Footer: *"Generated assistance, not legal advice."* Values read with low confidence print as `[to be verified]`. Errors: `404`, `409` (not processed), `422` (invalid `format`, FastAPI validation list).

## GET /api/buyers

```json
[
  {"id": 3, "name": "Deccan Agro Machines Pvt Ltd", "gstin": "36AAFCD5521Q1ZA", "synthetic": true,
   "profile": {"invoices_considered": 10, "median_days_late": 42.5, "pct_paid_late": 100.0,
               "pct_paid_over_30_late": 70.0, "trend": "worsening",
               "trend_detail": "median of last 3 = 62 days vs 35 days before", "label": "Slow",
               "note": "Based only on this supplier's own invoice history. Not a credit rating."}},
  …
]
```

- `label` ∈ `Reliable | Mixed | Slow | Insufficient history`. With fewer than `buyer_profile.min_history` (5) paid invoices, every number is `null`.
- `trend` ∈ `improving | worsening | stable | null` (needs ≥ 6 invoices).
- `synthetic: true` means seeded demo history. The UI must say **"synthetic demo data"**.

## GET /api/buyers/{id}/profile

This returns the buyer fields and the profile fields in one flat object. `404` `Buyer not found.`

```json
{"id": 1, "name": "Kaveri Auto Assemblies Pvt Ltd", "gstin": "27AABCK7712M1Z9", "synthetic": true,
 "invoices_considered": 10, "median_days_late": 0.5, "pct_paid_late": 50.0, "pct_paid_over_30_late": 0.0,
 "trend": "stable", "trend_detail": "median of last 3 = 1 days vs 0 days before", "label": "Reliable",
 "note": "Based only on this supplier's own invoice history. Not a credit rating."}
```

## GET /api/forecast

Query parameter: `days` = `30` (default) | `60`; any other value returns `400` `days must be 30 or 60.` Covers open, non-synthetic invoices only.

```json
{
  "as_of": "2026-11-23", "days": 30, "window_end": "2026-12-23",
  "totals": {"open": 22921.5, "expected_in_window": 0.0, "at_risk": 22921.5, "count": 1,
             "excluded_count": 0, "excluded_amount": 0},
  "buckets": [{"key": "overdue", "amount": 22921.5}, {"key": "next_30", "amount": 0.0},
              {"key": "days_31_60", "amount": 0.0}, {"key": "beyond_60", "amount": 0.0},
              {"key": "unknown", "amount": 0.0}],
  "invoices": [
    {"id": 61, "invoice_no": "SPC/26-27/0107", "buyer_id": 1, "buyer_name": "Kaveri Auto Assemblies Pvt Ltd",
     "amount": 22921.5, "due_date": "2026-10-13", "risk_tier": "Medium", "buyer_median_days_late": 0.5,
     "lag_days_applied": 0, "expected_date": "2026-10-13", "at_risk": true,
     "reasons": ["unpaid 41 day(s) after expected date"]}
  ],
  "excluded": [],
  "formula": "expected payment date = due date + buyer's median days late (0 if fewer than the minimum history); at risk = risk tier High, or due date unknown, or expected date already passed, or expected date beyond the window; suspected duplicates (C14 failed) and invoices whose total could not be read reliably are excluded",
  "note": "Illustrative forecast from synthetic demo history. Not a prediction of buyer payment."
}
```

- `buckets[].key` ∈ `overdue | next_30 | days_31_60 | beyond_60 | unknown`, always in that order. Buckets are measured from `as_of`, not from the window.
- `excluded[]` holds `{id, invoice_no, buyer_name, amount, reason}`, where `reason` ∈ `duplicate_suspect (C14 failed)` | `amount_unverified (total not read reliably)`. For `amount_unverified` the `amount` is `null`.
- Show `formula` in a tooltip and `note` as a banner (§9).

---

## Change policy

This file and `backend/app/schemas.py` are frozen contracts (CLAUDE.md). Any breaking change goes through A0 / the owner in a PR. That PR must update this file and bump `SCHEMA_VERSION` when a `schemas.py` model changes incompatibly. Adding a new optional response key is non-breaking.
