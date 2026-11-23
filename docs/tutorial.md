# VyapaarIQ: how it works

A complete guide to what VyapaarIQ does, how each part works, and why. Every term is defined
where it first appears and again in the **Glossary** (§13). Facts about law and rates carry a
reference (§14). Facts about the product point to the code or the doc that implements them.

> **Read this first.** VyapaarIQ is a demo built on **synthetic data**: every company, invoice and
> GSTIN is made up. Risk scores are illustrative, not a prediction of whether a buyer will pay.
> Legal figures (due dates, interest) are *estimates*, not legal advice. Verify them before any real
> use (§12).

---

## Contents

1. [The problem](#1-the-problem)
2. [What VyapaarIQ does, in one picture](#2-what-vyapaariq-does-in-one-picture)
3. [The documents behind an invoice](#3-the-documents-behind-an-invoice)
4. [Step 1: upload and classify](#4-step-1-upload-and-classify)
5. [Step 2: extraction and confidence](#5-step-2-extraction-and-confidence)
6. [Step 3: the 14 checks](#6-step-3-the-14-checks)
7. [Step 4: evidence graph, score and actions](#7-step-4-evidence-graph-score-and-actions)
8. [Step 5: due date and interest (the law)](#8-step-5-due-date-and-interest-the-law)
9. [Follow-ups, buyer reliability, forecast, dispute pack](#9-follow-ups-buyer-reliability-forecast-dispute-pack)
10. [Worked example: PKG07, end to end](#10-worked-example-pkg07-end-to-end)
11. [Architecture, data and quality](#11-architecture-data-and-quality)
12. [Limits and what to verify](#12-limits-and-what-to-verify)
13. [Glossary](#13-glossary)
14. [References](#14-references)

---

## 1. The problem

Indian **MSMEs** (micro, small and medium enterprises) often sell on credit to larger buyers and
then wait months for payment. Two figures show the scale:

- By June 2026 the government's **MSME Samadhaan** portal had recorded **2,56,892** delayed-payment
  applications from micro and small suppliers, with **₹55,244.29 crore** claimed [S-1]. These are
  claims filed since 2017, not amounts proven or recovered.
- An independent estimate puts the money stuck in delayed payments to MSMEs at **₹7.34 lakh crore**
  as of March 2024, over 4.6 % of India's GVA [S-2]. This is a model estimate, not official data.

When a buyer stalls, the supplier has to *prove* three things: that the buyer **ordered** the goods,
that the goods were **delivered**, and that the buyer **accepted** them. That proof is spread across
PDFs, phone photos and WhatsApp messages. The law gives micro and small suppliers strong rights:
a payment deadline, compound interest on late payment, and a dispute route (§8). Those rights are
only as strong as the paperwork behind them.

**VyapaarIQ** reads the paperwork for one invoice, cross-checks it, and shows the supplier:

- what is missing or inconsistent,
- what to fix first,
- the statutory due date and the interest building up,
- how a buyer has paid in the past,
- how much cash is at risk,
- and a ready-to-use evidence pack if the case becomes a dispute.

**What it does not do.** It does not predict whether a buyer will pay, give legal advice, send
messages, or file cases. Follow-up messages are drafts, and the dispute pack is something a human
files.

## 2. What VyapaarIQ does, in one picture

```
 files ──▶ classify ──▶ extract ──▶ 14 checks ──▶ score + tier ──▶ ranked actions
 (PDF/img)                │              │
                          │              ├──▶ due date + interest (MSMED rules)
                          │              └──▶ evidence graph
                          ▼
                  SQLite database ──▶ REST API ──▶ React UI
                                         │
                                         └──▶ follow-up drafts · buyer reliability ·
                                              cash-at-risk forecast · dispute pack
```

**Key idea: deterministic first, LLM second.** *Deterministic* means plain code that gives the
same output for the same input every time. All matching, scoring, due dates and interest are
deterministic Python. An **LLM** (large language model) may only help read documents. It never
changes a check result, a score, a date or an amount (`CLAUDE.md`, rule 1). That is why every
number on screen can be explained and tested.

## 3. The documents behind an invoice

A **package** is all the documents for one invoice. VyapaarIQ knows these document types:

| Document | What it proves | Key fields |
|---|---|---|
| **Purchase order (PO)** | The buyer ordered the goods, at these quantities, rates and payment terms | PO number, date, buyer, line items, total, payment terms |
| **Tax invoice** | The supplier billed the buyer | Invoice number and date, buyer and supplier **GSTIN**, PO reference, taxable value, GST, total, **IRN** |
| **Delivery challan / LR** | The goods were dispatched and, if stamped, received | Challan number, dispatch date, quantities, receiver's stamp or signature, received date |
| **E-way bill** | The goods moved legally on the road (needed above a value threshold) | E-way bill number, goods value |
| **GRN** (goods receipt note) or written acceptance | The buyer **accepted** the goods. This is the strongest proof | GRN number, GRN date, accepted quantities |
| **Contract** (optional) | Agreed payment terms | Payment-terms days |

Definitions:

- **GSTIN**: the 15-character Goods and Services Tax Identification Number of a business.
- **IRN**: Invoice Reference Number. The unique number a GST e-invoice gets from the government
  portal.
- **LR**: Lorry Receipt. The transporter's receipt, used instead of a challan.
- **Udyam number**: the MSME registration number (`UDYAM-XX-00-0000000`). It shows the supplier
  is a registered micro, small or medium enterprise.

## 4. Step 1: upload and classify

On **New package** the user drops in every file for one invoice: PDF, PNG or JPG, up to 15 MB each.
The backend stores them and **classifies** each one, meaning it decides what type of document the
file is:

1. **Keywords** on the first page (for example "TAX INVOICE", "GOODS RECEIPT NOTE"). Confidence 0.9.
2. Otherwise **the file name** (for example `PKG07_po.pdf`). Confidence 0.7.
3. Otherwise `other` (0.2), and the user can set the type by hand.

Code: `backend/app/extraction/base.py` (`classify`), `backend/app/services.py` (`create_package`).

## 5. Step 2: extraction and confidence

**Extraction** turns a document into structured fields. Every field has three parts
(`CLAUDE.md`, rule 3):

```json
{ "value": "2026-09-13", "confidence": 0.95, "source_page": 1 }
```

- **value**: what was read.
- **confidence**: how sure the reader is, from 0 to 1.
- **source_page**: where on the document it was found, so a human can check it.

Three **extractors** exist. The `EXTRACTOR` setting chooses one:

| Mode | How it reads | Used for |
|---|---|---|
| `text` (default) | PyMuPDF pulls the text layer out of a digital PDF, then patterns (regular expressions) pick out the fields | Real digital PDFs. Exact on our samples. A scanned image has no text layer, so its fields come back *uncertain* |
| `fixture` | Looks up the known answers for the 28 synthetic sample packages | Demos and tests. Offline and reproducible |
| `claude` | Sends the page to an Anthropic Claude model and asks for JSON fields only | Scans and messy documents. Optional, needs an API key. **Not used in the demo** (D-35) |

If one extractor fails, a **fallback chain** tries the next one (`claude → text → fixture`) and the
UI shows a "demo fallback" badge.

**Confidence gating.** A value read with confidence below **0.60** (`extraction.uncertain_below`)
is *never used in a calculation*. It is shown amber as "needs human check". Any check that depends
on it returns `uncertain` instead of guessing (D-3). This is why the evaluation shows **0
confidently wrong fields**: the system abstains rather than guesses (§11).

## 6. Step 3: the 14 checks

Each check returns:

- a **status**: `pass`, `fail`, `missing` or `uncertain`,
- a **severity**: `blocker`, `warning` or `info`,
- a one-line **detail**,
- the **evidence** it used.

A **blocker** is a problem that can sink a payment claim. A **warning** weakens it, and **info**
is a note. Tolerances come from `backend/app/rules/config.yaml`, never from code (rule 2).

| ID | Check | What it compares | Fails when | Severity |
|---|---|---|---|---|
| C01 | Invoice ↔ PO reference | Invoice's PO number vs the PO | No PO reference, PO not in the package, or the numbers differ | blocker |
| C02 | Amount reconciliation | Invoice taxable vs PO value; taxable + GST vs total | Taxable > PO + 1 %, or the GST math is off by more than ₹1 | blocker |
| C03 | Line items vs PO | Each line's quantity and rate vs the PO | Quantity above the PO, or rate above the PO by more than 0.5 % (a blocker above 10 %) | warning / blocker |
| C04 | Party consistency | Buyer name and GSTIN across all documents | They differ. Names are compared fuzzily, with a similarity of at least 0.90 | blocker |
| C05 | Delivery proof exists | Is there a challan or LR? | None in the package | blocker |
| C06 | Delivered ≥ invoiced | Challan quantity vs invoice quantity | Delivered less than invoiced | blocker |
| C07 | Receiving evidence | Receiver's stamp or signature on the challan | Missing | warning |
| C08 | Date logic | PO → invoice → challan order | Challan more than 7 days after the invoice, or PO dated after the invoice | warning |
| C09 | E-way bill | Goods value vs the ₹50,000 threshold | Above the threshold with no matching e-way bill | warning |
| C10 | GRN / acceptance | Is there written acceptance? | No GRN or written acceptance | blocker |
| C11 | Payment terms defined | Terms on contract, PO or invoice | No written terms (the 15-day rule then applies) | warning |
| C12 | Terms ≤ 45 days | Agreed terms vs the MSMED limit | More than 45 days for a micro/small supplier | warning |
| C13 | Supplier Udyam present | Udyam number on supplier documents | Missing | info |
| C14 | Duplicate invoice | Same invoice number + buyer already on record | Already exists | blocker |

A check reporting `missing` at `info` severity counts as **skipped**, and is shown grey. For
example, C06 and C07 cannot run when there is no challan. It is a consequence of another finding,
not a new one (D-22). Code: `backend/app/matching/checks.py`.

## 7. Step 4: evidence graph, score and actions

### Evidence graph

The **evidence graph** is the main screen. The invoice sits in the middle, and the PO, challan,
e-way bill, GRN and contract sit around it. Each link (an **edge**) is coloured by the checks
behind it:

| Edge status | Meaning |
|---|---|
| ✓ **matched** (green) | The checks on this link passed |
| ✕ **mismatch** (red) | A check failed, for example a quantity mismatch |
| ? **missing** (red, dashed) | The document is not in the package, for example no GRN |
| ! **uncertain** (amber) | A value was read with low confidence. It needs a human check |

Click a link to see why. The label names the check that decided it, failing checks first (D-34).
An unsure amount or number is written `? (verify)` (D-15). Code: `backend/app/matching/graph.py`,
`frontend/src/components/EvidenceGraph.jsx`.

### Readiness score and tier

**Readiness score** = 100 − the sum of penalties, kept between 0 and 100. It measures how
*claim-ready* the paperwork is. It does not predict payment.

| Finding | Penalty |
|---|---|
| Blocker | −25 (C10, missing acceptance: −30) |
| Warning | −10 |
| Uncertain | −5 |
| Info | 0 |

**Tier:** Low risk if the score is 85 or more, Medium from 60 to 84, High below 60. Every penalty
is listed on the *Actions & score* tab. Code: `backend/app/scoring/score.py`.

### Ranked actions

Each finding becomes an **action**: what to do, why, the **owner role** (sales, supplier accounts, dispatch)
and a **due-by date**. The date is 7 days before the payment due date, or *today* when that has
passed. Actions are ranked by severity and then by date. When the invoice is already overdue, the
UI says *"act now · payment overdue since …"* (B-8). The dashboard shows the top 5 actions across
all invoices. Code: `backend/app/scoring/actions.py`.

## 8. Step 5: due date and interest (the law)

This part encodes the **MSMED Act, 2006**, the Micro, Small and Medium Enterprises Development Act.
It protects **micro and small** suppliers. See §14 for the legal sources and their verification
status.

### Definitions

- **Acceptance**: the buyer actually accepts the goods, shown by a GRN or a written acceptance.
- **Deemed acceptance**: if the buyer raises no written objection within 15 days of delivery, the
  law treats the goods as accepted. MSMED s.2(b) takes the **day of actual delivery** as the day of
  deemed acceptance (D-11).
- **Appointed day**: the day after 15 days from acceptance or deemed acceptance (s.2(b)).
- **Agreed period**: the payment terms in a written agreement (the contract, PO or invoice).
  Under **s.15** it may not exceed **45 days** from acceptance or deemed acceptance. With no written
  agreement, the buyer must pay by the appointed day, which works out to **15 days**.
- **Interest (s.16)**: if the buyer pays late, interest is due at **three times the bank rate**
  notified by the RBI, **compounded with monthly rests**.
- **Bank Rate**: an RBI policy rate. It is set equal to the **MSF** (Marginal Standing Facility)
  rate, which is the repo rate + 0.25 %. The config uses **5.75 %** (as of 2026-10-07), so the
  interest rate is 3 × 5.75 = **17.25 % a year**.

### How VyapaarIQ computes the due date

1. **Acceptance date**, taking the first that applies:
   1. The **GRN date**.
   2. The **received date** on a stamped delivery challan.
   3. Otherwise **deemed** acceptance: the delivery date, labelled *deemed / estimated · verify*.
2. **Terms**: the written terms, capped at 45 days, or 15 days with no written terms.
3. **Due date** = acceptance date + terms. It is always labelled **estimated**, and the screen
   shows the rule that produced it.

A **medium** enterprise is outside the s.15/s.16 protections. Its written terms apply as written,
and without terms the 15-day figure is only an assumption, so it is marked uncertain (D-26).

### How it estimates interest

For each full 30-day month late, the amount compounds at rate/12. The remaining days accrue pro rata:

```
interest = P × (1 + r/12)^m × (1 + r/12 × d/30) − P
   P = invoice total, r = 3 × bank rate, m = full months late, d = remaining days
```

The formula is shown next to every interest figure. If the invoice total was not read reliably,
interest is **not computed** ("needs human check").

The follow-up drafts also mention the **buyer's tax rule**. Under the **Income-tax Act, 2025**
(in force from 1 April 2026), a buyer may deduct a payment to a micro or small supplier as an
expense only in the year it is actually paid, if it is paid after the s.15 deadline. This is
**s.37(2)(g)**; in the 1961 Act it was **s.43B(h)**. That rule gives suppliers leverage, and the
section number is configurable (D-13).

Code: `backend/app/rules/due_date.py`, `backend/app/rules/interest.py`,
`backend/app/rules/config.yaml`.

## 9. Follow-ups, buyer reliability, forecast, dispute pack

### Follow-up drafts

Five messages, timed relative to the due date: **D−7, D−1, D+3, D+10, D+25**. Each has a
**friendly** or **firm** tone, for email or WhatsApp. They are **drafts only, never sent** (D-10).

- They call the due date *estimated* and add a VERIFY note when it is deemed or uncertain (D-8).
- They mention Udyam status, s.16 interest and the dispute route only when C13 passed.
- The firm D+10 draft cites the 45-day rule.
- The last draft points to the dispute pack (D-9).

Code: `backend/app/followups/drafts.py`.

### Buyer reliability

This is computed from the **supplier's own past invoices** with that buyer. It is not a credit
rating, and the demo history is seeded and synthetic.

- **Median days late**: the middle value of (paid date − due date).
- **% paid late** and **% paid over 30 days late**.
- **Trend**: the median of the last 3 invoices against the earlier ones. More than 5 days worse is
  *worsening*; more than 5 days better is *improving*.
- **Label** (needs at least 5 invoices):
  - **Reliable**: median ≤ 5 days and ≤ 10 % over 30 days late.
  - **Slow**: median ≥ 20 days, or ≥ 40 % over 30 days late.
  - **Mixed**: everything in between.

Code: `backend/app/scoring/buyer_profile.py`.

### Cash-at-risk forecast (30 / 60 days)

**Expected payment date** = due date + the buyer's median days late (0 with too little history).
An open invoice is **at risk** if any of these is true:

- its tier is High,
- its due date is unknown,
- its expected date has already passed,
- its expected date falls beyond the window.

Suspected duplicates (C14) and unreadable totals are **left out** and listed, so totals never
double-count (D-7). The 60-day at-risk figure can be *lower* than the 30-day one: a longer window
means more invoices are expected inside it, so the tile reads "not expected by …" (D-32). The chart
puts amounts into buckets: overdue, next 30 days, 31–60 days, beyond 60 days, and unknown. On a
phone it opens as a table. Code: `backend/app/forecast/cash_at_risk.py`.

### Dispute evidence pack

A PDF (or Markdown, if the PDF cannot be built) for a delayed-payment reference. It has 9 sections:

1. Summary
2. Invoice facts
3. Document index
4. Timeline
5. Verification checks
6. Due date and reasoning
7. Estimated statutory interest
8. Missing or weak evidence
9. Suggested next step

Delayed-payment disputes go to the state's **MSE Facilitation Council**. New references are filed
on the **MSME ODR portal** (online dispute resolution). Older cases stay on **MSME Samadhaan** (see
§14). Unverified values print as `[to be verified]` (D-5). Code: `backend/app/dispute/pack.py`.

## 10. Worked example: PKG07, end to end

PKG07 is the demo invoice. Its package has the invoice, the PO and the challan, but **no GRN**.
The supplier is Shakti Precision Components; the buyer is Kaveri Auto Assemblies. Both are
fictional.

| Step | Result |
|---|---|
| Classify | 3 files: invoice, PO and challan, by keywords |
| Checks | 13 pass; **C10 GRN / acceptance: missing (blocker)** |
| Evidence graph | PO ✓ matched, challan ✓ matched, **GRN ? missing** (dashed) |
| Score | 100 − 30 (C10) = **70 → Medium** |
| Acceptance | No GRN, so the **challan's received date, 13 Sep 2026** |
| Terms | Written terms on the PO: **30 days** (within 45) |
| Due date | 13 Sep + 30 = **13 Oct 2026 (estimated)** |
| Interest at 23 Nov 2026 | 41 days late = 1 month + 11 days. P = ₹22,921.50, r = 17.25 % |
| | ₹22,921.50 × 1.014375 = ₹23,251.00; × (1 + 0.014375 × 11/30) = ₹23,373.55; **interest ≈ ₹452.05** |
| Action 1 | *Request GRN / acceptance from the buyer's receiving department.* Owner: sales. **Act now: payment overdue since 13 Oct 2026** |
| Follow-ups | D−7 to D+25 drafts; the firm D+10 cites the 45-day limit |
| Dispute pack | 9 sections; the missing-evidence section names the GRN |

## 11. Architecture, data and quality

| Layer | Technology | Where |
|---|---|---|
| Backend | Python 3.13, **FastAPI** (web API), **SQLModel** on **SQLite** (a database in one file), PyMuPDF (PDF reading), reportlab (PDF writing), rapidfuzz (fuzzy name matching) | `backend/app/` |
| Frontend | **React 19**, Vite, Tailwind CSS, React Router 7 | `frontend/src/` |
| API | 14 REST endpoints under `/api`. The contract is frozen at v1.0 (D-40) | `docs/api_contract.md` |
| Rules | Every legal value, tolerance and penalty | `backend/app/rules/config.yaml` |

**Synthetic data.** `samples/generate.py` builds **28 packages (133 PDFs)**: 6 clean, the rest
with one or two planted defects (missing GRN, short delivery, wrong GST math, duplicates, and so
on), and 5 made to look like phone scans. `samples/ground_truth.json` records the right answer for
every field and check. The generator is deterministic and reads its rules from `config.yaml` (D-28).

**Evaluation** (`eval/run_eval.py`, results in `eval/report.md`). In `text` mode:

| Measure | Result |
|---|---|
| Field accuracy | 93.5 % |
| Wrong-but-confident fields | **0** |
| Defect-detection precision | **100 %** |
| Recall | 88.5 % |
| Package verdicts | 24 / 28 correct, 4 abstained, 0 wrong |
| Due dates | 27 / 28 |

Every difference comes from a **scanned** document. Without OCR, a scan is marked *uncertain* and
sent for a human check rather than guessed (D-36). OCR means optical character recognition,
reading text from an image. In `fixture` mode everything is 100 %.

**Quality process.**

- **Tests:** 124 backend tests (pytest) and 43 frontend tests (vitest).
- **Browser run-through:** a scripted pass over all 28 packages (`frontend/scripts/ui_runthrough.mjs`).
- **Reviews:** every change goes through a pull request and a QA review, and only the owner merges (D-29).
- **Records:** bugs are in `docs/bugs.md`, and every source and decision is in `docs/references.md`.

**Hosted demo.** A password-protected copy runs on Render's free plan (`docs/deploy.md`, D-41).
One Docker container serves the API and the UI. HTTP Basic auth covers every path except the
health check, and HSTS keeps browsers on HTTPS. On every restart the demo data reloads from
scratch.

## 12. Limits and what to verify

- Accuracy is measured on **synthetic** documents; real scans are messier. The `claude` extractor
  for scans is optional and not measured (D-35).
- The readiness score and buyer labels are **illustrative**. Buyer history in the demo is seeded.
- Legal values are configurable and must be **verified** before real use: the bank rate, the
  deemed-acceptance reading, the s.37(2)(g) numbering and the ODR process. See §14 for what was
  checked and where.
- The app never sends messages or files disputes. A person does that.

## 13. Glossary

| Term | Meaning |
|---|---|
| **Acceptance** | The buyer's acceptance of delivered goods; the start of the MSMED payment clock |
| **Abstain** | Return `uncertain` instead of a guess when the input is not reliable |
| **Agreed period** | Payment terms in writing; at most 45 days for MSE suppliers (s.15) |
| **Appointed day** | The day after 15 days from acceptance or deemed acceptance (s.2(b)) |
| **Bank Rate** | RBI policy rate (= MSF rate); s.16 interest is 3 × this |
| **Blocker / warning / info** | Severity of a check finding: sinks a claim / weakens it / a note |
| **C01–C14** | The 14 deterministic verification checks (§6) |
| **Confidence** | 0–1 score on each extracted field; below 0.60 means *uncertain* |
| **Deemed acceptance** | Acceptance assumed by law when no written objection is raised within 15 days of delivery; dated the day of actual delivery |
| **Delivery challan** | Dispatch document travelling with the goods; stamped by the receiver on arrival |
| **Deterministic** | Same input → same output; plain code, no randomness or AI judgement |
| **Dispute pack** | The evidence document for a delayed-payment reference |
| **E-way bill** | GST document for moving goods by road above a value threshold (₹50,000 here) |
| **Evidence graph** | Diagram of the invoice linked to each supporting document, coloured by check results |
| **Extraction / extractor** | Turning a document into fields / the component that does it (`text`, `fixture`, `claude`) |
| **Fixture** | Known correct answers for the synthetic samples, used for demos and tests |
| **GRN** | Goods Receipt Note: the buyer's written record of goods received and accepted |
| **GSTIN** | 15-character GST registration number of a business |
| **HSTS** | Strict-Transport-Security header: tells browsers to use HTTPS only |
| **Income-tax Act, 2025 s.37(2)(g)** | Successor of old s.43B(h): a buyer deducts dues to MSE suppliers paid late only in the year of payment |
| **IRN** | Invoice Reference Number of a GST e-invoice |
| **LR** | Lorry Receipt from the transporter |
| **MSE / MSME** | Micro and Small Enterprises / Micro, Small and Medium Enterprises |
| **MSE Facilitation Council** | State body that hears delayed-payment references under MSMED s.18 |
| **MSF / repo rate** | RBI's Marginal Standing Facility rate (repo + 0.25 %) / its main policy rate |
| **MSMED Act** | Micro, Small and Medium Enterprises Development Act, 2006 |
| **MSME ODR portal** | Online Dispute Resolution portal where new delayed-payment references are filed |
| **MSME Samadhaan** | The earlier government portal for delayed-payment cases (pre-ODR) |
| **Package** | All documents for one invoice |
| **PO** | Purchase Order: the buyer's order with quantities, rates and terms |
| **Readiness score / tier** | 0–100 claim-readiness of the paperwork / Low, Medium, High band |
| **Skipped** | An info check reporting `missing` because its input document is absent |
| **Udyam number** | MSME registration number of the supplier |

## 14. References

### Product and decisions

- `BUILD_SPEC.md`: what to build.
- `task.md`: tasks and status.
- `CLAUDE.md`: the non-negotiable rules.
- `docs/references.md`: every source (R-1…R-7) and design decision (D-1…D-41), with who decided
  and why.
- `docs/architecture.md`, `docs/api_contract.md`, `docs/demo_script.md`, `docs/deploy.md`,
  `docs/release.md`, `docs/bugs.md`, `eval/report.md`.

### Statistics

- **[S-1]** PIB, *"From Enterprise to Empowerment: The MSME Story"*, 26 June 2026. MSME Samadhaan
  totals as on June 2026: 2,56,892 applications, ₹55,244.29 crore claimed, 58,148 disposed of by
  MSE Facilitation Councils.
  https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/jun/doc2026626903401.pdf
- **[S-2]** GAME, FISME and C2FO, *Delayed Payments Report 3.0*, released 26 Nov 2025. ₹7.34 lakh
  crore in delayed receivables as of March 2024 (> 4.6 % of GVA); down from ₹10.7 lakh crore (2022).
  - Report page: https://massentrepreneurship.org/delayed-payments/
  - Press release: https://c2fo.com/newsroom/delayed-payments-to-msmes-in-india-decrease-to-₹7-34-lakh-crore-but-challenges-persist-delayed-payments-3-0-report/

### Law and rates

Checked on 2026-11-24. **Primary** means the official text was read. **Secondary** means only a
summary or a third-party copy was available, usually because the official site refused automated
access.

- **[L-1] RBI Bank Rate 5.75 %: confirmed (primary).**
  - RBI Press Release 2026-2027/1264, *Monetary Policy Statement 2026-27: Resolution of the MPC,
    October 5–7, 2026* (7 Oct 2026): repo raised by 25 bps to **5.50 %**; SDF **5.25 %**; *"the
    marginal standing facility (MSF) rate and the Bank Rate at 5.75 per cent."*
    https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63742
  - MPC minutes (21 Oct 2026): https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63839
  - The rbi.org.in home page (23 Nov 2026) also shows Bank Rate 5.75 %.
  - So the s.16 rate is 3 × 5.75 = **17.25 %**.
- **[L-2] MSMED Act, 2006, ss. 2(b), 15, 16: confirmed (Act text).**
  - The text was read from the PRS-hosted copy of the Act as passed:
    https://prsindia.org/files/bills_acts/acts_parliament/2006/the-micro-small-and-medium-enterprises-development-act-2006.pdf
  - India Code copy: https://www.indiacode.nic.in/bitstream/123456789/7769/1/micro7.pdf
  - s.2(b), Explanation (ii): deemed acceptance is *"the day of the actual delivery of goods"* when
    no written objection is made within 15 days of delivery. This matches `deemed_acceptance_offset_days: 0`.
  - s.2(b): the appointed day is *"the day following immediately after the expiry of the period of
    fifteen days from the day of acceptance or the day of deemed acceptance."*
  - s.15: pay by the agreed date, or *"before the appointed day"* with no agreement. *"In no case"*
    may the agreed period *"exceed forty-five days"* from acceptance or deemed acceptance.
  - s.16: *"compound interest with monthly rests … at three times of the bank rate notified by the
    Reserve Bank."*
  - Caveat: a PIB factsheet mentions an MSMED (Amendment) Bill, 2026. Check whether any amendment
    has been enacted before real use.
- **[L-3] Income-tax Act, 2025, s.37(2)(g): confirmed by every source found (secondary text).**
  - The Act is in force from **1 April 2026**, per a PIB backgrounder (3 Sep 2025):
    https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/sep/doc202593626601.pdf
  - s.37(2)(g) covers an *"amount payable by the assessee to a micro or small enterprise beyond
    the time limit specified in section 15 of the [MSMED Act]"*. Such a sum is deductible only in
    the tax year it is actually paid. Unlike the other clauses, s.37(3) gives it no grace period up
    to the return date.
  - Official consolidated Act (it could not be opened automatically):
    https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf
  - No source supports "55(h)".
- **[L-4] MSME ODR portal: launch confirmed; the cut-over date is confirmed only through official-document summaries.**
  - The portal was unveiled at MSME Day on **27 June 2025** (PIB).
  - The Ministry of MSME Annual Report 2025-26 says *"all new delayed payment cases are being filed
    on the newly launched MSME ODR Portal from 15th October, 2025,"* and that it is being integrated
    with Samadhaan.
  - Portal: https://odr.msme.gov.in/
  - Scheme guidelines: https://odr.msme.gov.in/assets/pdf/MSE_Scheme_on_ODR_for_Delayed_Payment_Guidelines.pdf
  - Flow at a high level:
    1. Online application by the micro or small supplier.
    2. A voluntary pre-council stage, out of court.
    3. The MSE Facilitation Council stage: conciliation, then arbitration and an award, all online.
  - The exact current filing steps (for example the Udyam login) could not be read. **Verify on
    the portal before advising anyone.**
