# VyapaarIQ frontend

React + Vite + Tailwind v4. Pages per BUILD_SPEC §13; API per `docs/api_contract.md`.

```powershell
cd frontend; npm install; npm run dev   # http://localhost:5173 (backend on :8000)
npm test                                 # unit tests (vitest)
npm run lint; npm run build
```

`VITE_API_BASE` (see `.env.example`) points at the backend; default `http://localhost:8000`.
