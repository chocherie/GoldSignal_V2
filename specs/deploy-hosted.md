# Phase 2 — hosted deploy (API + static frontend)

## API (FastAPI)

- **Image:** `Dockerfile` at repo root builds `gold_signal.api.main:app`.
- **Env:** optional `FRED_API_KEY` for `DGS2` when 2Y missing from panel; `GOLD_DATA_DIR` if data is not at `/app/data`.
- **CORS:** `GOLD_CORS_ORIGINS` comma-separated list (e.g. `https://your-app.vercel.app`).
- **Health:** `GET /health`.

Example **Fly.io** / **Railway** / **Render:** set port `8000`, attach persistent volume or sync `data/` from your Bloomberg export job.

## Frontend (React / Vite)

- Build: `cd frontend && npm ci && npm run build`.
- Deploy `frontend/dist` to **Vercel**, **Netlify**, or S3+CloudFront.
- **Dev:** Vite proxies `/api` and `/health` to `http://127.0.0.1:8000` (see `frontend/vite.config.ts`).
- **Production:** set **`VITE_API_BASE`** to the API origin (no trailing slash), e.g. `https://your-api.fly.dev`, then rebuild. The UI uses `fetch` with `cache: 'no-store'` and refetches when you return to the tab; **Refresh** reloads from the API, **Shift+click Refresh** also calls `POST /api/v1/cache/invalidate` after CSV updates.

## Secrets

- Never commit `FRED_API_KEY` or Bloomberg workbooks; use platform secret stores.

## Invalidate cache

After refreshing raw CSVs on disk, call `POST /api/v1/cache/invalidate` or restart the API process.
