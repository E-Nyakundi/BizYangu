# BizYangu

**Biashara yako mikononi.**

The operating system for Kenyan SMEs. Real-time sales tracking, stock visibility, and M-Pesa reconciliation for dukas, hardware shops, boutiques, and stationery shops.

*Lewis Nyakundi — Architect · Engineer · Builder · Nairobi, KE*

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.x + DRF + Channels + Celery |
| Database | PostgreSQL 16 |
| Cache / Broker | Redis 7 |
| Frontend | Next.js 14 (App Router) + Tailwind + LN Design System |
| Mobile | Capacitor 6 → Android APK |
| Payments | Safaricom Daraja API (M-Pesa) |
| Auth | Phone OTP via Africa's Talking + SimpleJWT |

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16 (or Docker)
- Redis 7 (or Docker)

---

### 1. Clone & configure

```bash
git clone https://github.com/your-username/bizyango.git
cd bizyango
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
# Edit .env with your database credentials and API keys

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

# Build Next.js
npm run build

# Sync to Android
npx cap sync android

# Open in Android Studio
npx cap open android
```

---

## Migration Order

The apps have FK dependencies. Django resolves these automatically, but for reference:

```
business  →  accounts  →  catalog  →  transactions  →  inventory  →  payments
```

Run `python manage.py makemigrations` from the backend directory to generate all migrations at once. Django will detect dependencies and order them correctly.

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
bizyango/
├── backend/                  # Django project
│   ├── bizyango/             # Project config (settings, urls, asgi, celery)
│   │   └── settings/
│   │       ├── base.py
│   │       ├── development.py
│   │       └── production.py
│   ├── apps/
│   │   ├── accounts/         # Users, OTP auth
│   │   ├── business/         # Business profile, demo control
│   │   ├── catalog/          # Products, categories
│   │   ├── transactions/     # Sale engine
│   │   ├── inventory/        # Stock movements
│   │   ├── payments/         # M-Pesa integration
│   │   ├── reports/          # Dashboard data
│   │   └── notifications/    # Push, SMS, WhatsApp
│   ├── requirements/
│   ├── manage.py
│   ├── .env                  # Never commit this
│   └── .env.example
├── frontend/                 # Next.js app
│   ├── app/
│   │   ├── (auth)/login/
│   │   └── (app)/
│   │       ├── dashboard/
│   │       ├── sell/
│   │       ├── stock/
│   │       ├── reports/
│   │       └── settings/
│   ├── components/
│   │   ├── ui/               # LN Design System components
│   │   ├── sell/
│   │   ├── stock/
│   │   └── dashboard/
│   ├── lib/
│   │   ├── api.ts            # Axios + JWT interceptors
│   │   └── auth.ts
│   └── styles/
│       └── globals.css       # LN Design System CSS vars
├── docker-compose.yml        # postgres + redis for local dev
└── README.md
```

---

## Build Phases

| Phase | Scope | Status |
|---|---|---|
| 0 | Project skeleton — both servers running, Capacitor building | ✅ Complete |
| 1 | Auth (phone OTP) + Business setup wizard | 🔲 Next |
| 2 | Transaction engine — SELL MODE | 🔲 Planned |
| 3 | STOCK MODE + inventory management | 🔲 Planned |
| 4 | M-Pesa integration (Daraja STK Push + C2B) | 🔲 Planned |
| 5 | Owner dashboard + reports | 🔲 Planned |
| 6 | Prototype polish + test user deployment | 🔲 Planned |

---

*BizYangu — Lewis Nyakundi — June 2026*
