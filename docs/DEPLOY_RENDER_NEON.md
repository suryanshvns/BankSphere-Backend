# Deploy BankSphere API on **Render** + database on **Neon**

This guide assumes the **Git repo root is this `backend` folder** (or set **Root Directory** in Render to `backend` if the repo contains more than the API).

---

## 1. Neon (PostgreSQL)

1. Sign in at [https://neon.tech](https://neon.tech) → **Create project** (pick a region close to your Render region).
2. Open your project → **Dashboard** → **Connection details**.
3. Copy the **connection string** (role `neondb_owner`, database `neondb` or your DB name).

### URL you will use as `DATABASE_URL`

- Must include SSL, e.g.  
  `postgresql://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`
- If Neon shows a string without `sslmode`, **append** `?sslmode=require` (or `&sslmode=require` if the URL already has `?`).

### Optional: two URLs (only if migrations fail)

Neon sometimes documents a **direct** (non-pooled) host for migrations. If `prisma migrate deploy` errors with connection/prepared-statement issues, create a second secret in Render `DATABASE_URL_MIGRATE` with the **direct** URL and run migrations manually from your laptop against that URL once, or use Neon’s docs for “Prisma migrate”. For most setups, **one** `DATABASE_URL` with `sslmode=require` is enough on a long-running Render web service.

---

## 2. Render (Web Service)

### Create service

1. [https://dashboard.render.com](https://dashboard.render.com) → **New +** → **Web Service**.
2. Connect your Git provider and select the repo.
3. **Root Directory**: `backend` (if your repo root is not already `backend`).
4. **Runtime**: **Docker** (recommended; matches this repo’s `Dockerfile`).

### Instance / region

- Choose a **region** close to Neon (e.g. both in `us-east`).

### Health check

- **Health Check Path**: `/api/v1/health`

---

## 3. Environment variables on Render

Set these in the service → **Environment**:

| Key | Required | Example / notes |
|-----|----------|------------------|
| `DATABASE_URL` | **Yes** | Full Neon URL with `sslmode=require` |
| `SECRET_KEY` | **Yes** | Long random string (≥ 32 chars). Generate e.g. `openssl rand -hex 32` |
| `ENVIRONMENT` | Recommended | `production` |
| `CORS_ORIGINS` | **Yes** (for browser frontends) | Comma-separated list, **no spaces** unless each origin is trimmed in app — use exact URLs, e.g. `https://your-app.vercel.app,https://www.yourdomain.com` |
| `LOG_LEVEL` | Optional | `INFO` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | Default `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Optional | Default `14` |
| `PASSWORD_RESET_EXPIRE_MINUTES` | Optional | Default `60` |
| `PORT` | **No** | Render injects this automatically; the Dockerfile uses `${PORT:-8000}` |

**Note:** `pydantic-settings` reads `DATABASE_URL` from the env (maps to `database_url` in code). Same for `CORS_ORIGINS` → `cors_origins`.

---

## 4. Start command (Render) + migrations from your laptop

The **Dockerfile** runs **`python -m prisma generate`** at **container start** (not at image build), then starts Uvicorn. That avoids the common Render error: `prisma generate` failing during `docker build`.

**Migrations** are meant to be applied **from your machine** against Neon (same `DATABASE_URL` as Render):

```bash
cd backend
chmod +x scripts/sync_neon_db.sh
./scripts/sync_neon_db.sh
```

This runs `prisma generate` and `prisma migrate deploy`. Your `.env` must define `DATABASE_URL`. If the URL contains `&`, wrap it in **single quotes** in `.env`.

Optional: check status only:

```bash
./scripts/sync_neon_db.sh status
```

If you prefer migrations on every deploy instead, set Render **Docker Command** / **Start Command** to:

```bash
sh -c 'python -m prisma generate && prisma migrate deploy && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'
```

**Do not** run `scripts/seed.py` on every deploy unless it is idempotent. Seed **once** if you want demo users (see below).

---

## 5. One-time seed (optional)

After the first successful deploy:

1. Render dashboard → your service → **Shell** (if available on your plan), or run locally with **production** `DATABASE_URL`:

```bash
export DATABASE_URL='postgresql://...neon...?sslmode=require'
prisma migrate deploy   # if not already applied
python scripts/seed.py
```

This creates `admin@example.com` / `Admin123!@#` and `alice@example.com` / `User123456!` (see `README.md`). **Change passwords** in real production.

---

## 6. Verify

- **OpenAPI**: `https://YOUR-SERVICE.onrender.com/docs`
- **Health**: `https://YOUR-SERVICE.onrender.com/api/v1/health`

Frontend base URL for API calls:

`https://YOUR-SERVICE.onrender.com/api/v1`

---

## 7. Frontend checklist

1. Point the app to the Render URL + `/api/v1`.
2. Add that same origin (or your static site URL) to **`CORS_ORIGINS`** on Render — browsers block cross-origin calls if the frontend origin is not allowed.
3. Use **HTTPS** in production for `CORS_ORIGINS` (e.g. `https://app.vercel.app`).

---

## 8. Troubleshooting

| Issue | What to check |
|--------|----------------|
| DB connection failed | `DATABASE_URL` includes `sslmode=require`; password special chars are URL-encoded in the connection string. |
| CORS errors | `CORS_ORIGINS` includes the exact scheme + host + port of the frontend (e.g. `https://foo.vercel.app`). |
| 502 / crash on boot | Logs on Render; ensure `prisma migrate deploy` succeeds (fix DB URL / permissions). |
| Cold start slow | Render free tier spins down; first request after idle can be slow. |

---

## 9. Security reminders (production)

- Rotate `SECRET_KEY` if it was ever committed.
- Restrict Neon **IP allowlist** if you use it; Render outbound IPs can change on free tier — often people allow all Neon access via password + SSL instead.
- Do not expose `DATABASE_URL` or `SECRET_KEY` in the frontend.
