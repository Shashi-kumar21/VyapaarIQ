# VyapaarIQ

**Upload an invoice package → build an Invoice Evidence Graph → detect what could block or weaken
payment → explain the risk → recommend the next action.** Built for Indian MSME suppliers who sell
on credit (MSMED Act s.15/16 timelines). See [`BUILD_SPEC.md`](BUILD_SPEC.md) and [`task.md`](task.md).

> Demo project on **synthetic data with fictional companies**. Risk scores are illustrative, legal
> values are configurable and marked *verify*; nothing here is legal advice.

## Status

| Area | State |
|---|---|
| Rules: due date, deemed acceptance, 45/15-day terms, s.16 interest | ✅ tested |
| Checks C01–C14, readiness score, ranked actions, evidence graph | ✅ tested against ground truth |
| Extraction: `text` (PyMuPDF + regex), `fixture`, `claude` (optional) | ✅ (claude path tested offline only) |
| Synthetic generator: 28 packages / 133 PDFs, 5 phone-scan style | ✅ |
| REST API, SQLite, seed data | 🚧 next |
| React frontend, follow-ups, forecast, dispute pack, eval report | 🚧 planned |

## Quick start (Windows PowerShell)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt
.\.venv\Scripts\python samples\generate.py          # writes samples/out/ + ground_truth.json
cd backend; ..\.venv\Scripts\python -m pytest       # 32 tests
```

macOS/Linux: same steps with `python3.11+ -m venv .venv` and `.venv/bin/...`.

## Extractor modes (`EXTRACTOR`)

| Mode | What it does | Needs |
|---|---|---|
| `text` (default) | PyMuPDF text layer + regex heuristics; scanned pages return *uncertain* | nothing |
| `claude` | Claude reads text (or the PDF/image for scans) and returns validated JSON | `ANTHROPIC_API_KEY`, optional `LLM_MODEL` |
| `fixture` | Reads `samples/ground_truth.json`; guarantees the demo runs offline | nothing |

Fallback chain is `claude → text → fixture`; anything produced by a fallback is flagged
(`fallback: true`) so the UI can show a "demo fallback" badge.

## Design principles

- **Deterministic first, LLM second.** Checks, scores, due dates and interest are plain Python; an
  LLM may fill extracted fields or rephrase text but never changes a status or score.
- Every extracted field carries `value`, `confidence`, `source_page`. A field the extractor could
  not read makes dependent checks `uncertain` rather than pass/fail.
- Rule values live in [`backend/app/rules/config.yaml`](backend/app/rules/config.yaml).

## Layout

```
backend/app/{schemas.py, pipeline.py, rules/, matching/, scoring/, extraction/, llm/}
backend/tests/
samples/{generate.py, ground_truth.json}
docs/progress.md
```
