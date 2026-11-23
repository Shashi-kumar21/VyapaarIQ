# References

One place for **every external source** VyapaarIQ relies on and **every design decision** taken
while building it: who decided, when, where it is implemented, and why. Update this file in the
same PR whenever a rule value, a source or a decision changes.

> Legal and rate values are informational, configurable (`backend/app/rules/config.yaml`) and
> marked *verify*. Nothing here is legal advice. Most legal sources below are **secondary**
> (law and tax blogs, news). Check the primary text before any real use.

---

## 1. Sources

| ID | Topic | What we took from it | Sources | Confidence |
|---|---|---|---|---|
| R-1 | RBI Bank Rate | The MPC raised the repo rate by 25 bps to **5.50 %** on 2026-10-07. The Bank Rate (= MSF rate = repo + 25 bps) is therefore **5.75 %**. Earlier: repo 5.25 % (Dec 2025 – Oct 2026) | [SCC Online, 2026-10-09](https://www.scconline.com/blog/post/2026/10/09/rbi-hikes-repo-rate-to-5-50-percent-october-2026/) · [Corplaw Updates](https://www.corplawupdates.in/updates/rbi-repo-rate-hike-5-50-percent-october-2026) | Secondary. **Verify on [rbi.org.in](https://www.rbi.org.in)** (one source gave a different MSF figure) |
| R-2 | MSMED Act 2006 s.2(b): acceptance and deemed acceptance | With no written objection within 15 days of delivery, the **day of actual delivery** is the day of deemed acceptance. The "appointed day" is the day after 15 days from acceptance or deemed acceptance | [Taxclue: s.2 MSMED Act](https://www.taxclue.in/blog/section-2-msmed-act-2006-appointed-day-acceptance-and-deemed-acceptance) · [DC-MSME FAQs on delayed payments (PDF)](https://dcmsme.gov.in/old/faq/FAQs%20-%20Delayed%20Payments%20-%2027.12.2012.pdf) · [Taxmann FAQs on s.15](https://taxmann.com/post/blog/faqs-liability-of-buyer-u-s-15-of-msmed-act-to-make-timely-payments-to-mse-suppliers) | Government FAQ + secondary. Sources differ on whether the 15-day default means "within 15 days" or "by the appointed day". Our engine uses acceptance + 15 |
| R-3 | MSMED Act s.15 / s.16 | Agreed period **≤ 45 days** from acceptance or deemed acceptance; without a written agreement, pay by the appointed day. Interest is compound with monthly rests at **3 × the RBI bank rate** | R-2 sources · [BUILD_SPEC §2](../BUILD_SPEC.md) | Secondary + spec |
| R-4 | Income-tax rule on dues to micro/small suppliers | The Income-tax Act, 2025 is **in force from 2026-04-01**. The old s.43B(h) (1961 Act) maps to **s.37(2)(g)**: deduction allowed only on actual payment, with the time limit still from MSMED s.15. FY 2025-26 still falls under 43B(h) | [Taxupdate: 43B(h) → s.37](https://taxupdate.in/income-tax/893/section-43bh-msme-payment-disallowance-tax-audit-2026-section-37-income-tax-act-2025/) · [InCorpX: new section under the 2025 Act](https://www.incorpx.io/blog/section-43b-h-msme-payment-rule-new-section-2025-act) · [Wikipedia: Income-tax Act, 2025](https://en.wikipedia.org/wiki/Income-tax_Act,_2025) | Secondary. **One source says s.55(h)** ([Olambit](https://www.olambit.com/blog/section-43b-payment-deductions-new-act-2025/)). Verify against the Act text |
| R-5 | Delayed-payment references: MSME ODR portal | ODR portal launched 2025-06-27. **New references go only through ODR from 2025-10-15**; Samadhaan keeps cases filed before then | [Taxguru: ODR portal mandatory](https://taxguru.in/corporate-law/msme-odr-portal-mandatory-delayed-payments.html) | Secondary, consistent across sources. Verify the current process on the ODR portal / MSME ministry site |
| R-6 | Product scope and rules | Goal, checks C01–C14, score, due-date logic, forecast, dispute pack, evaluation | [BUILD_SPEC.md](../BUILD_SPEC.md) · [task.md](../task.md) · [CLAUDE.md](../CLAUDE.md) | Project spec |
| R-7 | Chart method | Form by the data's job; one hue validated for contrast; ≤ 24 px bars; value at the tip; tooltip and table view | Claude Code `dataviz` skill (palette validator run on `#2a78d6` vs the white card: all checks pass) | Tooling guideline |

---

## 2. Design decisions

**Decided by:** **Owner** = the project owner, after options were presented · **QA** = raised
in QA review and adopted · **Spec** = BUILD_SPEC / CLAUDE.md · **DEV** = implementation choice,
reviewed by QA. All dates are 2026-11-23 unless stated.

### Rules and legal values

| ID | Decision | By | Where | Why |
|---|---|---|---|---|
| D-1 | **Deterministic first, LLM second.** An LLM may only fill extracted fields or rephrase text; it never changes a status, score, date or amount | Spec | whole engine | Explainable, testable results |
| D-2 | Every rule value lives in `config.yaml`, never in code. The UI reads its thresholds from `/api/health` (`uncertain_below`, `min_history`) | Spec + QA | `rules/config.yaml`, `api/routes.py` | One place to change the law |
| D-11 | **Deemed acceptance = the delivery date** (`deemed_acceptance_offset_days: 0`; was 15). Due dates in deemed cases move 15 days earlier (PKG27: 2 Dec → 17 Nov 2026) | **Owner** | `config.yaml`; `samples/generate.py` reads the same value | Follows MSMED s.2(b) (R-2). Still labelled "deemed / estimated, verify" |
| D-12 | **Bank rate 5.75 %** as of 2026-10-07 (was 5.50 %). Interest goes from 16.5 % to 17.25 % a year (PKG07 at 2026-11-23: ₹432 → ₹452) | **Owner** | `config.yaml` `rbi` | R-1. Verify on rbi.org.in |
| D-13 | Drafts cite **"section 37(2)(g) of the Income-tax Act, 2025 (earlier section 43B(h) of the 1961 Act)"**, from config | **Owner** | `config.yaml` `legal_refs`; `followups/drafts.py` | R-4: the 2025 Act is in force. Configurable because the numbering still needs verifying |
| D-26 | The MSMED 45/15-day limits and s.16 interest apply only to micro/small suppliers. For `medium`, written terms apply as written, and 15 days without terms is an *uncertain assumption* | Spec + QA | `rules/due_date.py`, `rules/interest.py` | MSMED protections are for MSEs |

### Confidence and data quality (CLAUDE.md rule 3)

| ID | Decision | By | Where | Why |
|---|---|---|---|---|
| D-3 | A value read below `uncertain_below` (0.60) is **never used in a calculation**. The total becomes `None` and interest shows "not computable" | **Owner** (option A of 3) | `pipeline.known_value`, `services.process_package` | Never silently trust a low-confidence field. No schema change needed |
| D-4 | The buyer is identified only from a confidently read GSTIN or name, else from the upload's buyer-name hint, else left unlinked. **A buyer is never created from an unreadable name** | **Owner** | `services.resolve_buyer` | Keeps buyer history clean |
| D-5 | When the amount is unverified, drafts and the pack show **`[amount to be verified]` / `[to be verified]` with a VERIFY note**; they are not refused (409) | **Owner** | `followups/drafts.py`, `dispute/pack.py` | Usable in the demo without hiding the doubt |
| D-15 | Evidence-graph labels show **`? (verify)`** for unsure amounts or numbers, and that node becomes `uncertain` | QA | `matching/graph.py` | The graph is the demo screen |
| D-16 | Text extraction: a **truncated IRN** (`…`) is kept at confidence 0.4 (below threshold), and stamp text on the "Received By" line is stripped | DEV (found by eval) | `extraction/text_extractor.py` | Had produced 32 confidently wrong fields |

### Follow-ups, forecast, dispute pack

| ID | Decision | By | Where | Why |
|---|---|---|---|---|
| D-6 | An unpaid invoice whose **expected payment date has passed counts as "at risk"** | DEV, accepted by QA | `forecast/cash_at_risk.py` | Otherwise a 41-day-overdue invoice reads as "expected in window" |
| D-7 | **Suspected duplicates (C14 failed) and unverified amounts are excluded** from forecast totals and listed under `excluded`. The dashboard tier card uses the same population | QA | `forecast/`, `Dashboard.jsx` | No double counting; the totals agree |
| D-8 | Drafts always call the due date **"estimated"** and add a VERIFY note for deemed or uncertain dates. The "Udyam-registered" claim, s.16 interest and the ODR route appear only when C13 passed. The buyer is asked only for what the buyer can provide | QA | `followups/drafts.py` | No unsupported claims in a letter to a buyer |
| D-9 | Drafts whose send date has passed are **kept and marked past**. The last one points to the dispute pack | QA | `followups/drafts.py` | Useful reference without false "7 days from now" wording |
| D-10 | Follow-ups are **drafts only**: never sent by the app. Every draft carries a `DRAFT` header and the owner copies it into email or WhatsApp | Spec | `followups/drafts.py`, `FollowupsPanel.jsx` | No message reaches a buyer without a human reading it |
| D-17 | Dispute pack: one structure, Markdown + reportlab PDF, **Markdown fallback** if the PDF fails. Core fonts get ASCII substitutes (₹ → "Rs.", ↔ → "<->"). CORS exposes `Content-Disposition` and `X-Pack-Format` | Spec + DEV | `dispute/pack.py`, `main.py` | Always exportable; correct file name in the browser |

### Evaluation (`eval/run_eval.py`)

| ID | Decision | By | Why |
|---|---|---|---|
| D-14 | `uncertain` on a defective package = a miss (FN). On a good package = neither TN nor FP | DEV, accepted by QA | No credit for abstaining |
| D-18 | Package verdict is **3-way** (blocker / abstained / clean); abstentions are never counted as correct. PKG14 is labelled "abstained" | QA | An earlier "27/28" overclaimed |
| D-19 | Skipped checks (`missing` on an info check, e.g. C06/C07 with no challan) are excluded from TP and recall; fields correct because absent are reported separately | QA | Recall 88.5 %, not 90 % |
| D-20 | Fallback between extractors is **off** during evaluation; `run_eval` never regenerates samples | DEV + QA | Measure each mode alone; never rewrite ground truth |

### Frontend and API

| ID | Decision | By | Why |
|---|---|---|---|
| D-21 | The UI rounds INR **half to even, on the exact binary value**, like Python | QA | The UI and the pack never disagree by a rupee |
| D-22 | Info checks reporting `missing` are shown grey as **"skipped"** and are not counted as needing attention | QA | They are consequences, not findings |
| D-23 | `doc_types` must be a JSON list (≤ one entry per file, known types or null), else **400** | QA | Was a 500 or silently accepted |
| D-24 | New `GET /api/actions` gives the dashboard's top actions, ranked like inside an invoice | QA | §13 "top 5 actions" without N requests |
| D-25 | Forecast chart: **ordered horizontal bars, one validated hue, no legend**, value at the tip, tooltip, formula and table view | DEV (R-7) | Magnitude over ordered buckets |
| D-32 | At-risk tiles read **"not expected by <date>"**, not "until <date>": the 60-day figure is lower than the 30-day one by definition (more invoices fall inside a longer window) | DEV (T4.13) | It looked like a bug on stage |
| D-33 | On a phone (< 640 px) the forecast **starts in table view**; the 1000-unit chart would shrink its text below 7 px | DEV (T4.13, R-7) | Readable on mobile without a second chart layout |
| D-34 | Text the user reads uses one date style (`23 Nov 2026`, `app/fmt.d`), including action titles. Evidence-graph edges list the **failing check first**, because the label shows one id | DEV (T4.13) | "before 2026-11-23" and "mismatch · C05…" (real cause C07) were found in the run-through |

### Data and process

| ID | Decision | By | Why |
|---|---|---|---|
| D-27 | Seeded history uses **fixed per-buyer lateness lists** (shuffled), so Reliable / Mixed / Slow labels are stable | DEV | Random draws mislabelled a "Mixed" buyer |
| D-28 | `samples/generate.py` is **deterministic** (fixed PDF dates on scans) and reads its rules from `config.yaml` | DEV (found in the fresh-clone test) | It used to rewrite `ground_truth.json` on every run |
| D-29 | Workflow: feature branch → PR into `main` → QA posts `VERDICT` → **only the owner merges**. **No stacked PRs** | **Owner** | Review before anything reaches `main`. Stacking once left #6/#7 off `main` (fixed by #9) |
| D-30 | Communication with the owner is in Romanised Hindi; code, commits and PRs are in English | **Owner** | Preference |
| D-31 | The GitHub repository is **private** | **Owner** | |
| D-35 | **No API key for the demo** (T0.3): the demo runs on `fixture` (and `text`); the `claude` extractor and LLM explanations (T3.7, T3.8, T4.6, T4.7) stay optional and unmeasured | **Owner** | No network or key risk on stage, no API cost |
| D-36 | **Scans keep abstaining** without OCR: in `text` mode a scanned document is `uncertain` (needs human check), never guessed. No local OCR dependency is added. Every `text`-mode eval difference is such a scan (PKG02/06/09/14/21) | **Owner** (T5.3) | Keeps 0 confidently wrong fields; local OCR would add a heavy dependency and new error risk |
| D-37 | Every processed package logs one line (package id, invoice id, document count, extractor, fallback, ms; failures log only the error type) and the invoice header shows "processed in …" | DEV (T3.10) | Timing visible without logging document text (CLAUDE.md rule 4) |
| D-38 | **npm audit before the demo**: apply only non-breaking patches (react-router-dom 6.30.6 closes the *high* advisories; vitest 3.2.7). The remaining moderate react-router advisories (no user-controlled paths, no SSR) and the dev-only vitest/tinypool ones wait for React Router 7 + Vitest 5 after `v0.1-demo` | **Owner** | No breaking upgrade right before the demo; see `docs/release.md` |
| D-39 | After the tag: **React Router 7.18.5 (`react-router`) + Vitest 5.1.0**. Pick releases at least two weeks old that contain the fixes; `npm audit` = 0 | **Owner** (post-demo order) | Closes the advisories D-38 deferred, without the newest-release supply-chain risk |

---

## 3. Verify before any real use

- [ ] Bank Rate on rbi.org.in (D-12, R-1)
- [ ] Deemed-acceptance reading of s.2(b), and the 15-day default (within 15 days vs by the appointed day) (D-11, R-2)
- [ ] s.37(2)(g) numbering in the Income-tax Act, 2025 text (D-13, R-4)
- [ ] Current ODR portal filing process (R-5)
- [ ] The opening statistic in `docs/demo_script.md` (needs a real, sourced figure)
