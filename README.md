# BizYangu

Mobile-first business management for Kenyan SMEs — dukas, hardware shops,
boutiques, salons, bars, and similar small businesses. Replaces notebooks,
manual M-Pesa checks, and guesswork with real-time sales tracking, stock
visibility, and payment reconciliation.

Built by [Biashara Systems](https://biasharasystems.co.ke).

For product scope, phase status, and the pilot go-live checklist, see
[`BizYangu_Master_Plan.md`](./BizYangu_Master_Plan.md) — that's the single
source of truth for planning; this README is just for running the thing.

## Stack

- **Backend:** Django 5 + Django REST Framework + Channels (WebSockets)
- **Frontend:** Next.js 14 (App Router) + Tailwind + Zustand + TanStack Query
- **Mobile:** Capacitor 6 (Android wrapper around the Next.js frontend)
- **Data:** PostgreSQL + Redis + Celery
- **Payments/SMS:** Safaricom Daraja (M-Pesa), Africa's Talking (OTP)

## Repo layout

```
backend/      Django project (apps/: accounts, business, catalog, core,
              customers, inventory, knowledge, notifications, payments,
              reports, transactions)
frontend/     Next.js app + Capacitor Android project
knowledge/    Business-type taxonomy (JSON) — categories, brands, units
              per business type. Read live by backend/apps/knowledge/,
              not seeded into the DB.
docker-compose.yml   Full local stack: postgres, redis, backend, frontend
```

## Prerequisites

- Docker + Docker Compose (recommended path — see below)
- Or, for running services natively: Python 3.12+, Node 18+, PostgreSQL 16,
  Redis 7

## Quick start (Docker)

```bash
# 1. Backend env
cp backend/.env.example backend/.env
# edit backend/.env — at minimum generate a SECRET_KEY and a Fernet key:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. Start everything
docker-compose up -d

# 3. Create an admin user
docker-compose exec backend python manage.py createsuperuser
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Admin: `http://localhost:8000/admin/` (or whatever `ADMIN_URL_PATH` is
  set to in `.env`)

Useful compose commands:

```bash
docker-compose up -d postgres redis   # infra only, run backend/frontend natively
docker-compose logs -f backend        # tail Django logs
docker-compose logs -f frontend       # tail Next.js logs
docker-compose down                   # stop everything
docker-compose down -v                # stop + wipe DB volume
```

**Note on `knowledge/`:** the backend loader resolves the taxonomy path as
`Path(BASE_DIR).parent / 'knowledge'`, i.e. a sibling of `backend/` on
disk. `docker-compose.yml` already bind-mounts `./knowledge:/knowledge` to
preserve that relationship inside the container — without it, every
`/api/v1/knowledge/` endpoint 500s with `FileNotFoundError` even though
the same code works fine outside Docker.

## Running natively (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements/development.txt
cp .env.example .env   # fill in SECRET_KEY, DB creds, Fernet key (see above)
python manage.py migrate
python manage.py createsuperuser
daphne -b 0.0.0.0 -p 8000 bizyangu.asgi:application
```
Use `daphne`, not `manage.py runserver` — the app uses Channels for
WebSockets (payment status, live reports), which needs an ASGI server.

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Celery (background jobs — STK-push timeout cleanup, etc.):**
```bash
celery -A bizyangu worker -B   # combined worker+beat, fine for local dev
```

## Environment variables

Full list with inline explanations lives in `backend/.env.example`. Key
ones to know about:

| Variable | Purpose |
|---|---|
| `DEV_OTP_BYPASS` | `True` accepts a fixed `000000` OTP with no SMS sent — local dev only. **Must be `False` before any real deploy.** |
| `MPESA_ENV` | `sandbox` or `production` — switches the Daraja base URL |
| `MPESA_CREDENTIALS_ENCRYPTION_KEY` | Fernet key encrypting per-business M-Pesa credentials at rest — generate a real one per environment, don't reuse |
| `ADMIN_URL_PATH` | Django admin path — set to a random slug in production so `/admin/` doesn't exist |
| `FCM_SERVICE_ACCOUNT_JSON` | Optional — leave empty to disable push notifications; degrades gracefully |
| `SENTRY_DSN` | Optional — leave empty to disable error reporting; nothing crashes if unset |

Production values and the full go-live sequence are covered in
[`BizYangu_Master_Plan.md`](./BizYangu_Master_Plan.md) §7.

## Mobile (Android)

The frontend is wrapped with Capacitor for Android distribution.

```bash
cd frontend
npm run build
npx cap sync android
npx cap open android   # opens Android Studio
```

`NEXT_PUBLIC_API_URL` is baked in at `next build` time — rebuild the APK
after changing which API it points to; it won't pick up a new URL at runtime.

## Contributing / session workflow

This is currently a solo build. If picking a session back up, see
[`BizYangu_Master_Plan.md`](./BizYangu_Master_Plan.md) §11 for the list of
files to bring into context, and §1 for current phase status.
