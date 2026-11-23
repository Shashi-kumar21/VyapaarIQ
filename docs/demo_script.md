# VyapaarIQ: 3-minute demo script

Task T5.8. Rehearse it twice before recording (Definition of Done, BUILD_SPEC §18). Every number
below was checked on the running app with the setup shown. If your screen shows something
different, the setup differs: re-run it rather than reading out the numbers from this page.

## Setup (once, about 5 minutes before)

Run the demo from the tag **`v0.1.1-demo`**. It has the evidence-graph click fix (B-11) and the
phone layout. The older `v0.1-demo` draws a black focus box when the GRN link is clicked.

The tag is checked out into a **separate folder** (a git worktree), so your own working copy
stays on its branch. The commands assume the clone is called `VyapaarIQ`; adjust the name if yours differs.

```powershell
# from the repo root, after the README quick start (the .venv is reused from this clone)
git fetch --tags; git worktree add ..\VyapaarIQ-demo v0.1.1-demo
cd ..\VyapaarIQ-demo
..\VyapaarIQ\.venv\Scripts\python samples\generate.py    # sample PDFs are not in git (deterministic)
cd frontend; npm ci; cd ..
$env:EXTRACTOR = "fixture"           # offline and reproducible; say so on stage
$env:VYAPAARIQ_TODAY = "2026-11-23"  # pins "today" so due dates and interest match this script
$env:VYAPAARIQ_DB = "$PWD\backend\data\demo.db"
Remove-Item $env:VYAPAARIQ_DB -ErrorAction SilentlyContinue
cd backend; ..\..\VyapaarIQ\.venv\Scripts\python -m app.seed   # synthetic buyer history
..\..\VyapaarIQ\.venv\Scripts\uvicorn app.main:app             # API on :8000 (keep this terminal open)
# second terminal
cd ..\VyapaarIQ-demo\frontend; npm run dev                  # UI on http://localhost:5173
# after the demo, from the VyapaarIQ folder (--force: generated files are untracked): git worktree remove --force ..\VyapaarIQ-demo
```

Before going on stage:
- Upload **PKG01** (clean) and **PKG20** (terms over 45 days) on *New package*, so the dashboard
  is not empty.
- Keep `VyapaarIQ-demo\samples\out\PKG07\` open in Explorer: invoice, PO and challan, **no GRN**.
- Browser at 100 % zoom, about 1366 px wide. Close other tabs.

## Script

| Time | Screen | Say (short) | Do |
|---|---|---|---|
| **0:00–0:30** | Dashboard | "MSME suppliers sell on credit and wait. When a buyer stalls, the supplier must prove order, delivery and acceptance, and the proof is scattered across PDFs and WhatsApp. **[One real statistic on delayed payments to MSMEs, with its source: VERIFY the figure and source on the day; do not use an unchecked number.]**" | Point to the banner: synthetic demo data, illustrative, not legal advice |
| **0:30–1:30** | New package → Invoice detail | "Here is one invoice's paperwork: invoice, PO, challan. Notice there's no GRN." | Drag in the 3 PDFs from `PKG07` → **Process package** → it opens the invoice |
| | Evidence graph | "VyapaarIQ reads each document and cross-checks them. PO matched, challan matched, but **the GRN link is missing**: there is no written acceptance from the buyer." | Click the dashed **GRN** link: *"No GRN or written acceptance… acceptance can only be deemed"* |
| | Header | "That weakens the claim. Readiness is **70, Medium**, and every point lost is listed." | *Actions & score* tab: **C10 missing (blocker) −30** |
| | Actions | "The first thing to do: request the GRN or acceptance from the buyer's receiving team. The payment is already overdue since 13 October." | Point to action 1: *act now · payment overdue since 13 Oct 2026* |
| **1:30–2:15** | Header → details | "The statutory due date is **13 Oct 2026**: acceptance from the challan's received date plus 30 days of written terms. It is an estimate, and it shows the rule it used. Estimated MSMED interest to today is about **₹452** (3 × the 5.75 % bank rate), with the formula shown. Not legal advice." | Expand *How the due date and interest were worked out* |
| | Follow-ups tab | "Drafts for D−7 through D+25, friendly or firm. They are never sent." | **Generate drafts** → switch **Firm** → show D+10 citing the 45-day rule → **Copy body** |
| | Dispute pack tab | "And a dispute-ready evidence pack: timeline, document index, checks, due date, interest, missing evidence." | Scroll the preview → **Download PDF** |
| **2:15–2:45** | Dashboard | "Across all open invoices: what is at risk in the next 30 and 60 days, and the top actions to work on first." | Point to the *cash at risk* tiles, the forecast chart (hover the overdue bar), *Top actions* |
| | Buyers | "Reliability from this supplier's own history. Seeded demo history, not a credit rating." | Show the Reliable / Mixed / Slow rows |
| **2:45–3:00** | `eval/report.md` | "We measured it on 28 synthetic packages. Real extraction got every field right or flagged it for a human: **zero confidently wrong fields**, 100 % precision on defects. Scans need the Claude extractor, which isn't measured yet. Next: Tally/Zoho sync, WhatsApp sending with consent, and ODR filing support." | Show the summary table |

## If something goes wrong

| Problem | Recover |
|---|---|
| The status chip says *Backend unreachable* | The uvicorn terminal was closed. Restart it; the UI recovers on reload |
| Port 5173 is busy | Vite stops (`strictPort`) instead of moving to another port, which CORS would reject. Close the other dev server |
| Numbers differ from this page | `VYAPAARIQ_TODAY` or `EXTRACTOR` is not set in the uvicorn terminal. Fix it and re-upload |
| PKG07 shows up as a duplicate (C14) | It was uploaded twice into the same DB. Delete the demo DB and re-seed (Setup) |
| PKG27 changes the dashboard | Since D-11 (deemed acceptance = delivery date) PKG27 is due 17 Nov 2026, so on the demo date it is overdue and moves into *at risk*. The script does not use it; if it was uploaded, delete the demo DB and re-seed |
| A black box appears around a graph link after a click | You are on `v0.1-demo`. Check out `v0.1.1-demo` (Setup). On stage, a click on an empty part of the page removes it |
| A live upload fails | Use the backup recording (below) |

## Backup recording

A captioned, silent recording of the whole script is made by `frontend/scripts/record_demo.mjs`.
It uses the same setup, with PKG01 and PKG20 already uploaded, and produces a WebM of about 2 minutes.
Narrate over it live if needed. Keep the video next to the slides, outside the repo, and never commit it.
You can also record a run yourself with the Windows Game Bar (`Win+Alt+R`).
