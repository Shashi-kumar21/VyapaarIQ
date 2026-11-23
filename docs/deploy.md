# Hosted demo on Render (shareable link)

Owner decision **D-41** (2026-11-24): share a link so others can try the demo. The link runs on
**Render's free plan**, behind a **shared password**. The live demo still runs on the laptop
(`docs/demo_script.md`), because that works offline.

## What the link runs

One Docker web service (`Dockerfile`, `render.yaml`) serves the API and the built UI from the same
address. The defaults are baked into the image:

| Setting | Value | Why |
|---|---|---|
| `EXTRACTOR` | `fixture` | Same numbers as the demo script. Only the 28 sample packages are read (see *Limits*) |
| `VYAPAARIQ_TODAY` | `2026-11-23` | Due dates and interest match the script |
| `DEMO_BOOTSTRAP` / `DEMO_PRELOAD` | `1` / `PKG01,PKG20` | Every start on an empty DB seeds the synthetic history and preloads two invoices |
| `VYAPAARIQ_DB` | `/tmp/vyapaariq-demo.db` | The free plan has no persistent disk, so a restart returns to the clean demo state |
| `STATIC_DIR` | `/app/frontend/dist` | The UI is served by the API (`VITE_API_BASE=/` at build time) |
| `DEMO_USER` / `DEMO_PASSWORD` | `demo` / *(secret)* | HTTP Basic auth on everything except `/api/health`, which Render's health check uses |

`DEMO_PASSWORD` is entered in the Render dashboard only. It is **never** committed, and the app
never logs it. With no password set, the gate is off. Never deploy without it.

## Image hardening

- **Base images are pinned to exact releases:** `node:22.23.4-slim` and `python:3.13.17-slim`. Bump
  them on purpose, in a PR.
- **Python packages:** the image installs only `backend/requirements-runtime.txt`, at the exact
  versions in `backend/constraints-runtime.txt`, the same versions the test suite runs with.
  pytest, httpx and the optional Claude client are left out, because `fixture` mode never calls
  Claude. Local development still uses `backend/requirements.txt`, which includes the runtime set.
- **Password gate:** every response carries `Strict-Transport-Security`, because Basic auth is only
  safe over HTTPS. Render terminates TLS and redirects `http://` with a 301. Only the `lifespan`
  scope passes the gate without a password. WebSocket connections are closed, since the app has
  none.
- **Possible follow-up:** PyMuPDF 2.x pulls in `onnxruntime` and `numpy`, which makes the image
  larger. Pinning PyMuPDF 1.x could shrink it, but the extractor would need re-testing first.

## Steps (owner, one time, about 15 minutes)

1. Sign in at [render.com](https://render.com) with GitHub. When Render asks for repository
   access, allow **only** `Shashi-kumar21/VyapaarIQ`. The repo is private (D-31).
2. **New → Blueprint**, then pick the repo. Render reads `render.yaml` and shows one free web
   service, `vyapaariq-demo`.
3. When asked for `DEMO_PASSWORD`, enter a strong password (for example 4 random words) and keep
   it in your password manager.
4. **Apply**. The first build takes about 5–10 minutes: npm build, pip install, sample generation.
5. Open the service URL, for example `https://vyapaariq-demo.onrender.com`. Sign in as `demo` with
   your password. The dashboard shows 2 invoices, and the status chip reads
   *API ok · extractor fixture · today 2026-11-23*.
6. Share the link and the password **in separate messages**.

`autoDeploy` is off. After a PR is merged and checked, use **Manual Deploy → Deploy latest
commit**. To take the link down, **Suspend** the service, or delete it.

## Limits (tell people before they open the link)

- **The first visit can take 30–60 seconds.** A free service sleeps after 15 minutes without
  traffic.
- **Data resets** whenever Render restarts or redeploys the service, and Render may restart free
  services at any time. Uploads are not kept.
- **Synthetic data only.** Do not upload real invoices. In `fixture` mode the app reads only the 28
  sample packages (`samples/out/PKG*`). To let people try an upload, share a sample folder such as
  PKG07, which has no GRN.
- There is no login beyond the shared password. Anyone who has both can upload files (15 MB limit
  per file).

## Check a deploy

```powershell
curl.exe -s https://<service>.onrender.com/api/health          # 200, extractor fixture, today 2026-11-23
curl.exe -s -o NUL -w "%{http_code}" https://<service>.onrender.com/api/invoices   # 401 without the password
```

The same image was checked locally before the PR, without Docker, by running the steps the
`Dockerfile` runs:

- Without the password: 401.
- With it: the dashboard shows 2 invoices.
- A PKG07 upload: 1 of 14 checks needs attention.
- The PDF download works, a deep-link reload works, and the console shows no errors.

A shell note for anyone repeating this: in Git Bash, `VITE_API_BASE=/` is rewritten to a Windows
path. Build from PowerShell, or set `MSYS_NO_PATHCONV=1`. The Linux Docker build is not affected.

Sources (checked 2026-11-24): [Render free tier](https://render.com/docs/free) · [Blueprint YAML reference](https://render.com/docs/blueprint-spec).
