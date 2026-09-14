# Deploying MineGuard

Target architecture (€0/month, always-on):

| Piece | Host | Notes |
|---|---|---|
| Web (Next.js) | **Vercel** (Hobby, free) | Git-push deploys |
| API (FastAPI) | **Koyeb** (Free instance) | Docker deploy, always-on; 512 MB RAM |
| DB + Auth + Storage | **Supabase** (free) | Already migrated; add one storage bucket |

---

## 0. Prerequisites

- The `feature/visual-compliance-loop` branch merged to `main`
- A [Koyeb](https://app.koyeb.com) account (free, no credit card)
- A [Vercel](https://vercel.com) account (free)
- Your existing Supabase project

## 1. Supabase: create the uploads bucket

1. Supabase Dashboard → your project → **Storage** → **New bucket**
2. Name: `lease-uploads` — keep it **Private** (the API proxies downloads so auth is enforced)
3. No RLS policies needed: all access happens with the service-role key server-side.

## 2. Koyeb: deploy the API

1. Koyeb → **Create App** → **GitHub** → pick this repo.
2. Build settings:
   - **Builder:** Docker
   - **Build context:** `/` (repository root)
   - **Dockerfile:** `services/api/Dockerfile`
3. Service settings:
   - **Port:** `8000`
   - **Health check:** HTTP GET `/health`
   - **Instance:** Free (0.1 vCPU / 512 MB)
4. Environment variables (**Settings → Environment**):

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | `postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres` (from Supabase → Connect; **must** keep the `postgresql+psycopg://` scheme) |
   | `AUTH_MODE` | `supabase` |
   | `SUPABASE_URL` | `https://<ref>.supabase.co` |
   | `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API → service_role |
   | `SUPABASE_STORAGE_ENABLED` | `true` |
   | `API_CORS_ORIGINS` | `https://<your-app>.vercel.app` |
   | `INVITE_REDIRECT_URL` | `https://<your-app>.vercel.app/auth/callback` |
   | `API_ENV` | `production` |
   | `GEMINI_API_KEY` | your key |
   | `RESEND_API_KEY` / `RESEND_FROM_EMAIL` | your keys (enables alerts + reminders) |

5. Deploy. First boot runs `alembic upgrade head` against Supabase automatically
   (the DB is already migrated, so it will be a no-op) and then binds uvicorn.
6. Note the public URL, e.g. `https://<app>-<org>.koyeb.app` — check `/health/ready`
   returns the PostGIS version.

> Koyeb free instances give ~512 MB RAM. The API idles around 200–300 MB;
> keep demo photos small (≤ ~2 MB) to stay comfortable during vision calls.

## 3. Vercel: deploy the web

1. vercel.com → **Add New… → Project** → import the repo.
2. **Root Directory:** `apps/web` (framework auto-detects Next.js).
3. Environment variables:

   | Variable | Value |
   |---|---|
   | `NEXT_PUBLIC_API_BASE_URL` | `https://<app>-<org>.koyeb.app` |
   | `NEXT_PUBLIC_SUPABASE_URL` | `https://<ref>.supabase.co` |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Settings → API → anon |

4. Deploy → `https://<your-app>.vercel.app`.

## 4. Supabase Auth: point redirects at production

Dashboard → **Authentication → URL Configuration**:

- **Site URL:** `https://<your-app>.vercel.app`
- **Redirect URLs:** add `https://<your-app>.vercel.app/auth/callback`

## 5. Verify

1. `https://<koyeb>/health/ready` → PostGIS version JSON
2. Open the Vercel URL → landing → sign in (your bootstrap admin) → dashboard loads
3. Open a lease → **Inspections & AI findings** → upload a site photo →
   findings appear and the compliance score dips
4. Acknowledge → resolve → the score recovers; check Supabase **Storage →
   lease-uploads** shows the photo

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| API boot loop mentioning `auth` | `AUTH_MODE=supabase` without `SUPABASE_URL` or `SUPABASE_JWT_SECRET` |
| Web loads but every API call 401s | anon/service keys swapped, or `NEXT_PUBLIC_API_BASE_URL` missing |
| Upload 502 with “Storage backend error” | bucket `lease-uploads` missing or `SUPABASE_STORAGE_ENABLED` unset |
| Vision 502 | `GEMINI_API_KEY` invalid or quota exhausted |
| CORS errors in browser console | `API_CORS_ORIGINS` doesn't exactly match the Vercel URL (scheme + host, no trailing slash) |
