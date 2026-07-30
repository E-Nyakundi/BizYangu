# BizYangu

**Biashara yako mikononi.**

The operating system for Kenyan SMEs. Real-time sales tracking, stock
visibility, and M-Pesa reconciliation for dukas, hardware shops, boutiques,
bars, salons, wholesalers, and more.

*Lewis Nyakundi — Architect · Engineer · Builder · Nairobi, KE*

---

## Where things stand (July 2026)

Phases 0 through 5.6 of the build are complete and in daily use: auth,
business setup, the sell flow, stock/inventory, M-Pesa STK push, the owner
dashboard + reports (including a live WebSocket feed), and full staff
management (invite/list/remove via a `/join` acceptance flow). A dedicated
infrastructure audit (sessions/JWT/Redis/N+1 queries) has also been run and
its fixes applied.

**The living build plan is `BizYangu_Build_Plan_v3.md`** — read that first
for anything past Phase 5. `v1` and `v2` stay in the repo as history; don't
build against them. Session-specific writeups (`PHASE5_HANDOFF.md`,
`PHASE6_AUDIT_FINDINGS.md`) have the detailed "what changed and why" for
their respective sessions.

**`knowledge/`** holds the first draft of the product taxonomy (Build Plan
v3, Phase 8) for 9 business types — see `knowledge/README.md`. Brand names
in there are placeholders pending review; category/subcategory structure is
the current priority.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.1 + DRF + Channels + Celery |
| Database | PostgreSQL 16 |
| Cache / Broker / Channel layer | Redis 7 — now used consistently for all three (see `PHASE6_AUDIT_FINDINGS.md` — this wasn't always true) |
| Frontend | Next.js 14 (App Router, static export) + Tailwind + LN Design System |
| Mobile | Capacitor 6 → Android APK |
| Payments | Safaricom Daraja API (M-Pesa STK Push + C2B, IP-allowlisted webhooks) |
| Auth | Phone OTP via Africa's Talking + SimpleJWT (rotation + blacklist on refresh/logout) |
| Error tracking | Sentry (off by default — set `SENTRY_DSN` in `.env` to enable) |

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16 (or Docker)
- Redis 7 (or Docker) — **required**, not optional: Channels, Celery, the
  Django cache, and every DRF rate limit all depend on it now

---

### 1. Clone & configure

```bash
git clone https://github.com/your-username/bizyangu.git
cd bizyangu
```

### 2. Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements/development.txt

# Configure environment
cp .env.example .env
# Edit .env with your database credentials and API keys.
# New optional vars worth knowing about (all have safe defaults):
#   SENTRY_DSN               — blank = error tracking disabled, no crash
#   ADMIN_URL_PATH            — defaults to admin/, set a random slug in prod
#   SENTRY_TRACES_SAMPLE_RATE, SENTRY_ENVIRONMENT — only matter if SENTRY_DSN is set

# Database — option A: native PostgreSQL (already installed)
# Create role and database in psql:
#   CREATE ROLE lewis WITH LOGIN PASSWORD 'your-password';
#   CREATE DATABASE bidness OWNER lewis;
#   GRANT ALL PRIVILEGES ON DATABASE bidness TO lewis;

# Database — option B: Docker (postgres + redis only)
# cd .. && docker-compose up -d && cd backend

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start server
python manage.py runserver 0.0.0.0:8000
```

Backend available at: `http://localhost:8000`
Health check: `http://localhost:8000/api/v1/health/`
Admin: `http://localhost:8000/admin/` in dev (path is env-configurable — see
`ADMIN_URL_PATH` above; don't leave it at the default in production)

---

### 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Edit NEXT_PUBLIC_API_URL if your Django port differs

# Start dev server
npm run dev
```

Frontend available at: `http://localhost:3000`

---

### 4. Capacitor (Android)

```bash
cd frontend

# Build Next.js — confirm out/ actually has a fresh timestamp before
# syncing (a failed/stale export silently ships old assets otherwise —
# see the note on `next build`'s known cosmetic /_document error below)
npm run build
Get-Item .\out\index.html | Select LastWriteTime   # PowerShell; `stat out/index.html` on macOS/Linux

# Sync to Android
npx cap sync android

# Build the APK
cd android
.\gradlew.bat assembleDebug   # or ./gradlew assembleDebug on macOS/Linux

# Install (uninstall first if replacing an existing build, not just -r —
# clears any cached JS bundle the webview may have pinned)
adb uninstall <your.app.id>
adb install app\build\outputs\apk\debug\app-debug.apk
```

> **Known cosmetic build issue:** `npm run build` can throw
> `PageNotFoundError: Cannot find module for page: /_document` after
> "Compiled successfully" / "Linting and checking validity of types" — this
> is Next 14.2.x's static-export pipeline choking on its own fallback
> error-page prerender, not a real failure. Confirm `out/` regenerated with
> a fresh timestamp (above) rather than trusting the log output alone.

---

## Migration Order

The apps have FK dependencies. Django resolves these automatically, but for
reference:

```
business  →  accounts  →  catalog  →  transactions  →  inventory  →  payments  →  reports
```

`reports` has no models of its own (all computed) — nothing to migrate
there. Run `python manage.py makemigrations` from the backend directory to
generate all migrations at once; Django detects dependencies and orders
them correctly.

---

## ngrok Setup

```bash
# Install ngrok, authenticate
ngrok config add-authtoken YOUR_TOKEN

# Start tunnel (use a static domain for M-Pesa webhooks)
ngrok http --domain=your-static-domain.ngrok-free.app 8000
```

Update `MPESA_CALLBACK_URL` in `.env` with your ngrok domain.

---

## Project Structure

```
bizyangu/
├── backend/                  # Django project
│   ├── bizyangu/             # Project config (settings, urls, asgi, celery)
│   │   ├── asgi.py           # ws/mpesa/{business_id}/ + ws/dashboard/{business_id}/
│   │   ├── urls.py           # admin path is env-configurable (ADMIN_URL_PATH)
│   │   └── settings/
│   │       ├── base.py       # CACHES/CHANNEL_LAYERS/CELERY all share one Redis
│   │       ├── development.py
│   │       └── production.py # Sentry init lives here (no-op if SENTRY_DSN unset)
│   ├── apps/
│   │   ├── accounts/         # Users, OTP auth, StaffInvite (join flow)
│   │   ├── business/         # Business profile, staff list/remove, demo control
│   │   ├── catalog/          # Products, categories
│   │   ├── transactions/     # Sale/refund/void engine
│   │   ├── inventory/        # Stock movements
│   │   ├── payments/         # M-Pesa integration (STK push, IP-allowlisted webhooks)
│   │   ├── reports/          # Dashboard + reports (computed, no models) + WS consumer
│   │   └── notifications/    # Push, SMS, WhatsApp
│   ├── requirements/
│   ├── manage.py
│   ├── .env                  # Never commit this
│   └── .env.example
├── frontend/                 # Next.js app (static export, output: 'export')
│   ├── app/
│   │   ├── login/
│   │   ├── setup/
│   │   ├── onboarding/products/
│   │   ├── join/              # staff invite acceptance — outside (app) layout
│   │   │                       # deliberately, since that layout auto-redirects
│   │   │                       # anyone without a business to /setup
│   │   └── (app)/
│   │       ├── dashboard/     # live WebSocket revenue/txn feed
│   │       ├── sell/
│   │       ├── stock/
│   │       ├── reports/       # daily/period/products/losses, WhatsApp EOD share
│   │       ├── payments/
│   │       └── settings/      # business profile edit + staff invite/list/remove
│   ├── components/
│   ├── lib/
│   │   ├── api.ts             # Axios + JWT interceptors + apiErrorMessage()
│   │   ├── auth.ts
│   │   ├── business.ts        # business profile + staff management client
│   │   └── reports.ts
│   └── styles/
│       └── globals.css        # LN Design System CSS vars
├── knowledge/                 # Product taxonomy lexicon (Build Plan v3, Phase 8)
│   ├── README.md              # structure, review status, what's still needed
│   ├── business_types.json
│   ├── categories.json
│   ├── subcategories.json
│   ├── units.json
│   └── templates/              # one file per business type
├── docker-compose.yml          # postgres + redis for local dev
├── BizYangu_Build_Plan_v3.md   # ← the living plan; read this, not v1/v2
├── BizYangu_Build_Plan_v2.md    # history only
├── BizYangu_Build_Plan_v1.md    # history only
├── PHASE5_HANDOFF.md            # dashboard/reports session writeup
├── PHASE6_AUDIT_FINDINGS.md      # sessions/JWT/Redis/N+1 audit writeup
├── CHANGES.md
└── README.md
```

---

## Build Phases

Full detail lives in `BizYangu_Build_Plan_v3.md` — this table is a quick
reference, not the source of truth.

| Phase | Scope | Status |
|---|---|---|
| 0 | Project skeleton | ✅ Complete |
| 1 | Auth (phone OTP) + Business setup wizard | ✅ Complete |
| 2 | Transaction engine — SELL MODE | ✅ Complete (barcode scan not wired) |
| 3 | STOCK MODE + inventory management | ✅ Complete |
| 4 | M-Pesa integration (Daraja STK Push + C2B) | ✅ Complete (PDF statement import deferred) |
| 5 | Owner dashboard + reports (+ live WebSocket feed) | ✅ Complete (automatic 9pm EOD trigger deferred — manual WhatsApp dispatch works) |
| 5.5 | Settings + staff invite/list/remove | ✅ Complete |
| 5.6 | Security/hygiene pass (rate limiting, Sentry, admin URL) | ✅ Complete |
| 6 | Sessions/JWT/Redis/N+1 audit | ✅ Complete — see `PHASE6_AUDIT_FINDINGS.md` |
| 7 | Reports: growth & profit graphs | 🔲 Next |
| 8 | Knowledge Base Curation (taxonomy) | 🟡 First draft done, awaiting content review — see `knowledge/README.md` |
| 9 | Sell-without-inventory + progressive catalog growth | 🔲 Planned |
| 10 | Demo-driven taxonomy refinement | 🔲 Planned |
| 11 | Perishability tracking | 🔲 Planned |
| 12 | Creditor UI / customer ledger | 🔲 Planned |
| 13 | Cross-business sub-niche detection | 🔲 Planned (data-gated) |
| 14 | More settings | 🔲 Planned (awaiting requirements) |
| — | E-commerce / B2B marketplace | 🔲 Separate initiative, own planning session — not sequenced against the phases above |

---

*BizYangu — Lewis Nyakundi — Nairobi, Kenya*
