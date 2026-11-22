# CLAUDE.md — VyapaarIQ project rules

Read `BUILD_SPEC.md` (what to build) and `task.md` (when, who) first. Section
numbers (§) refer to `BUILD_SPEC.md`.

## Stack
- Backend: Python 3.11+ (venv uses 3.13), FastAPI, SQLModel on SQLite, PyMuPDF, reportlab, rapidfuzz.
- Frontend: React + Vite + Tailwind.
- LLM: Anthropic API, model from `LLM_MODEL`, key from `ANTHROPIC_API_KEY`. Optional.

## Non-negotiables
1. **Deterministic first, LLM second.** Matching, scoring, due dates, interest
   are plain Python. LLM output may only fill extracted fields or rephrase
   text; it must never change a check status or a score.
2. Rule values (tolerances, penalties, 45/15 days, bank rate) live in
   `backend/app/rules/config.yaml`. Never hard-code them.
3. Every extracted field carries `value`, `confidence`, `source_page`.
   Low confidence => `uncertain`, never silently trusted.
4. No secrets in git. No logging of full extracted document text.
5. Legal outputs are labelled "estimated / not legal advice / verify".
6. Fictional companies only in samples.

## Ownership (§17)
| Agent | Owns |
|---|---|
| A0 Architect | `BUILD_SPEC.md`, `task.md`, `CLAUDE.md`, `backend/app/db`, `backend/app/schemas.py`, merges |
| A1 Document intelligence | `backend/app/extraction`, `backend/app/llm`, `samples/` |
| A2 Backend & risk | `backend/app/{api,matching,rules,scoring,forecast,dispute}`, `backend/tests` |
| A3 Frontend & QA | `frontend/`, `eval/`, `docs/demo_script.md` |

`schemas.py` and `docs/api_contract.md` are frozen contracts; change them only
through A0.

## Commands (run from repo root, Windows PowerShell)
```powershell
py -3.13 -m venv .venv; .\.venv\Scripts\pip install -r backend\requirements.txt
.\.venv\Scripts\python samples\generate.py            # synthetic packages + ground_truth.json
cd backend; ..\.venv\Scripts\python -m pytest -q      # tests
cd backend; ..\.venv\Scripts\uvicorn app.main:app --reload   # API on :8000
cd frontend; npm install; npm run dev                 # UI on :5173
```

## Env vars
- `EXTRACTOR` = `claude` | `text` | `fixture` (default `text`, auto-fallback to `fixture`)
- `ANTHROPIC_API_KEY`, `LLM_MODEL` (only for `claude`)
- `VYAPAARIQ_DB` (default `backend/data/vyapaariq.db`)

## Definition of a finished task
Tests pass, `task.md` checkbox ticked, one line in `docs/progress.md`.
