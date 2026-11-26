# Release: v0.1-demo (T5.10)

Pre-release checks run by DEV on 2026-11-23 against `main` at `f5a9a26` (after PRs #14 and #15).
**Tagged:** annotated `v0.1-demo` at `c5ec290`, pushed 2026-11-23 at the owner's request. Later changes (React Router 7 / Vitest 5, P2 UI fixes) are on `main` after the tag.

## Checklist

| Check | Result | How |
|---|---|---|
| Backend tests | ✅ green | `cd backend; ..\.venv\Scripts\python -m pytest -q` |
| Frontend tests, lint, build | ✅ vitest 40 passed, eslint clean, `vite build` OK | `cd frontend; npm test; npm run lint; npm run build` |
| Full UI run-through, all 28 packages | ✅ 28/28, exit 0, no console errors, no page overflow. Re-run after the dependency patch below | `frontend/scripts/ui_runthrough.mjs` (see `docs/bugs.md`) |
| Eval | ✅ unchanged: `text` 93.5 % fields, 0 confidently wrong; `fixture` 100 % | `.\.venv\Scripts\python eval\run_eval.py` |
| Debug code | ✅ none: no `print`, `breakpoint`, `pdb` in `backend/app` (the seed CLI prints a summary by design); no `console.log` or `debugger` in `frontend/src` | `grep` |
| Logging | ✅ only ids, counts, timings, model id and request id; never document text (CLAUDE.md rule 4, D-37) | review of every `log.*` call |
| Secrets in git history | ✅ none found in all 53 commits (all branches): no Anthropic, AWS or GitHub tokens, no private keys | `git log --all -p` scanned for key patterns |
| Tracked env / data files | ✅ only `.env.example` and `frontend/.env.example`, both without values. `.env`, `*.db` and `backend/data/` are git-ignored | `git ls-files` |
| Python dependencies | ✅ no known vulnerabilities | `pip-audit -r backend/requirements.txt` (in a separate venv) |
| npm dependencies | ⚠️ patched; 5 remain, none in the demo path (see below) | `npm audit` |

## npm audit (owner decision D-38)

**Fixed in this release:**

- `react-router-dom` 6.28.0 → **6.30.6** (`@remix-run/router` 1.21.0 → 1.23.4). This closes the
  **high** XSS / open-redirect advisories.
- `vitest` 3.2.4 → 3.2.7.
- `package.json` minimums are raised to these versions, so a fresh install cannot pick the old ones.

**Remaining, accepted until after the demo.** Each needs a breaking major upgrade:

| Package | Severity | Why it does not affect the demo |
|---|---|---|
| `react-router` 6.x | moderate | Two advisories. (1) An open redirect via a backslash in `<Link>` / `useNavigate`: every path in the app is a fixed route or a numeric id from our own API, never user input. (2) SSR hydration: we do not use SSR. Fix: React Router 7 |
| `vitest` / `@vitest/mocker` / `tinypool` | moderate / critical | **Dev-only.** They run only during `npm test` on a developer machine and need attacker-controlled test options or mock registration. They are not part of the built app. Fix: Vitest 5 |

**Next step after the demo:** upgrade to React Router 7 and Vitest 5 in one PR, then repeat the
run-through.

## After v0.1-demo: dependency upgrade (D-39)

Done in the first post-demo PR, **after** the tag:

- `react-router-dom` 6.30.6 is replaced by **`react-router` 7.18.5**. In v7, `react-router-dom` only re-exports `react-router`. The v6 `future` flags are removed, because their behaviour is now the default.
- **`vitest` 5.1.0** (from 3.2.7).
- Both versions are more than two weeks old, and both contain the advisory fixes.
- `npm audit`: **0 vulnerabilities**.
- Verified with vitest 40, eslint and build. The full run-through gave 28/28, exit 0, with no console errors or warnings. Routes, the 404 page, deep links and the back button were also checked in the browser.

## Tags

| Tag | Commit | What it is |
|---|---|---|
| `v0.1-demo` | `c5ec290` | First demo-verified build (the checks above) |
| `v0.1.1-demo` | `283f137` | + evidence-graph click fix (B-11) and the updated demo script |
| `v0.1.2-demo` | `4ca4d57` (tag object `641086f`) | + redesigned UI (D-43: sidebar, hover cards, How it works page; #31) and the demo script re-checked on it (#32). Contains `4c50dad`, `e4bdd71`, `445a3e5`. **Current demo build**; backup video re-recorded from it |

## Tagging (owner)

```powershell
git checkout main; git pull
git tag -a v0.1-demo -m "VyapaarIQ v0.1 demo"
git push origin v0.1-demo
```

## Still open, owner side

- Backup screen recording of the demo script (`docs/demo_script.md`, T5.8).
- A sourced figure for the opening statistic in `docs/demo_script.md`.
- The verify list in `docs/references.md` §3: bank rate, s.2(b) reading, s.37(2)(g) numbering, ODR process.
