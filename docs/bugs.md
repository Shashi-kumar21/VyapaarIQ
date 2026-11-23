# Bugs: full UI run-through (T4.13)

**Run:** 2026-11-23, DEV. Demo setup from `docs/demo_script.md` (`EXTRACTOR=fixture`,
`VYAPAARIQ_TODAY=2026-11-23`, fresh DB + seed). A scripted browser (Playwright, Chromium)
uploaded **all 28 packages through the New package page**, in order. For each one it:

- compared every check status, the due date and the acceptance basis with `samples/ground_truth.json`;
- opened all five tabs (Checks, Actions & score, Documents, Follow-ups, Dispute pack);
- generated follow-up drafts;
- downloaded the dispute-pack PDF.

It then opened Dashboard and Buyers at 1366 px and 375 px. Every view was screenshotted, and
the console was watched for errors.

The script is committed as **`frontend/scripts/ui_runthrough.mjs`** (manual; not part of `npm test`).
Its header gives the exact steps. It exits 1 if any package has an issue.

**Severity:** P0 = blocks the demo or shows a wrong number · P1 = misleading on screen ·
P2 = cosmetic. **Owner tag** = who fixes it (§17): A2 backend & risk, A3 frontend.

## Result

| | |
|---|---|
| Packages uploaded via the UI | 28 / 28 |
| Check statuses equal to ground truth | 28 × 14 = 392 / 392 |
| Due date + acceptance basis equal to ground truth | 28 / 28 |
| Tabs opened without an error box | 140 / 140 |
| Follow-up drafts generated | 28 × 5 |
| Dispute-pack PDFs downloaded (valid `%PDF`) | 28 / 28 |
| Browser console errors | 0 |
| Horizontal page overflow (Dashboard, Buyers; desktop and phone) | 0 px |
| **Open P0 bugs** | **0** |

## Bugs found and fixed in this PR

| ID | Sev | Owner | Where | Bug | Fix |
|---|---|---|---|---|---|
| B-1 | P2 | A2 | Dashboard top actions, Actions tab | The C10 action title read "…before **2026-11-23**", while every other date on screen is "23 Nov 2026" | Action titles use `app.fmt.d` (D-34) |
| B-2 | P2 | A2 | Checks tab, C11 | "Written payment terms found on the **po**" | Source labels map to "PO" / "invoice" / "contract" |
| B-3 | P1 | A2 | Evidence graph (PKG27) | The challan edge read "mismatch · **C05…**", but C05 passed: the real cause is C07 (no receiver stamp). The label shows only the first check id | Edges list failing or uncertain checks first (D-34) |
| B-4 | P1 | A3 | Dashboard stat tiles | "Cash at risk · 60 days" (₹66,85,085) was **lower** than the 30-day figure (₹80,39,017) under the hint "until <date>". That is correct by definition, but it looks like an error | Hint now reads "not expected by <date>" (D-32) |
| B-5 | P1 | A3 | Dashboard chart at 375 px | Chart text scaled to about 6 px and could not be read | The table view is open by default below 640 px (D-33) |

Each fix has a regression test. B-3 also covers a failing *info* check, which turns an edge red too (QA #13 nit):

- **Backend:** `tests/test_ground_truth.py::test_ui_text_from_runthrough` and `::test_edge_leads_with_failing_check_of_any_severity`.
- **Frontend:** the `ForecastChart` tests in `components/panels.test.jsx`, plus the stat-hint assertion in `pages/pages.test.jsx`.

A second full run after the fixes was clean: 28/28, no issues.

## Open (not fixed; none blocks the demo)

| ID | Sev | Owner | Where | Note |
|---|---|---|---|---|
| B-6 | P2 | A3 | Dashboard invoice table at 375 px | Only Invoice and Buyer are visible. Amount, due date, score and tier are reached by scrolling the table sideways; the page itself does not overflow. A card layout on phones would read better |
| B-7 | P2 | A3 | Dashboard chart at 375 px | The small chart still shows above the table. It could be hidden on phones while the table is open |
| B-8 | P2 | A2 | Top actions | Actions whose target date is already past show "due by 23 Nov 2026" (today), because the target is clamped to today. This is intended (do it now), but "overdue since …" would say more |
| B-9 | P2 | A3 | Buyers, trend column | On Windows "↘ improving" renders as a blue emoji, while "↗ worsening" renders as plain text. The glyphs should match (an SVG icon or a text-presentation selector) |
| B-10 | P2 | A3 | `/invoices/<seeded id>` (typed by hand) | A seeded history invoice shows "Something went wrong · This invoice has not been processed yet" with a useless **Try again**. The UI has no link to it; a calm "not processed" state would be better |

## Not a bug (checked)

- **Duplicate invoices** (PKG23/24 re-use 0117/0118) appear twice in the invoice table. C14 flags them, and the forecast and tier card leave them out ("2 invoice(s) left out"), as D-7 intends.
- **PKG27 changes the dashboard** once uploaded (due 17 Nov 2026, now overdue, D-11). The demo script does not use it, and its recovery table says so.
- **High tier shows 0 invoices** while ₹80 lakh is "at risk". The tier comes from the readiness score; at-risk also counts invoices whose expected payment date has passed or falls after the window (D-6). Both labels say what they measure.
