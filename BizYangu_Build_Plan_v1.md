# BizYangu — Comprehensive Build Plan v1.0
**The Operating System for Kenyan SMEs**
*Lewis Nyakundi — Architect · Engineer · Builder · Nairobi, KE*
*Last updated: June 2026 — CONFIDENTIAL*

---

## 0. Context & Constraints

### What we are building
BizYangu is a mobile-first business management platform for Kenyan SMEs — dukas, hardware shops, boutiques, stationery shops, and similar small retail businesses. It replaces notebooks, manual M-Pesa checks, and guesswork with real-time sales tracking, stock visibility, and payment reconciliation.

### Prototype scope
The first deployable version runs on the founder's laptop (served via ngrok), accessed by 5–10 test users recruited from the field interview cohort. No subscription billing in this phase. The goal is real daily usage generating real data, not a polished product.

### Prototype must-haves (everything else comes later)
1. Business setup + progressive product catalog onboarding
2. SELL MODE — record a sale, cash or M-Pesa
3. Stock tracking — quantities updated automatically on each sale
4. End-of-day summary — revenue, transaction count, M-Pesa vs cash split
5. Owner dashboard — today at a glance

### Design authority
All UI follows the **LN Design System v1.0**:
- Typography: Space Grotesk (display/UI) + JetBrains Mono (code/labels/metadata)
- Dark-first. Base: `#0A0A0A`. Primary accent: `#00E5C4` (teal). Error: `#FF4D6D`
- 12-column grid, base-8 spacing, border radius tokens per component type
- Kiswahili-first copy layer. English fallback.

---

## 1. Tech Stack — Final Decisions

### Backend
| Layer | Technology | Reason |
|---|---|---|
| Framework | Django 5.x | Home ground. Rapid model-to-API. Strong ORM for transaction integrity. |
| API | Django REST Framework | Serializers, viewsets, JWT auth, versioning. |
| Database | PostgreSQL | Relational. ACID transactions. Audit log support. |
| Async tasks | Celery + Redis | M-Pesa webhook processing. Scheduled reports. Notifications. |
| Realtime | Django Channels + WebSocket | Live dashboard updates. M-Pesa confirmation push to POS screen. |
| Auth | django-allauth + SimpleJWT | OTP via Africa's Talking. JWT for API sessions. Role-based access. |
| M-Pesa | Safaricom Daraja API | STK Push, C2B, statement reconciliation. Sandbox → production. |
| SMS/OTP | Africa's Talking API | OTP delivery. End-of-day WhatsApp summary. |
| Dev tunnel | ngrok | Prototype hosting. M-Pesa webhook receiver on localhost. |

### Frontend
| Layer | Technology | Reason |
|---|---|---|
| Framework | Next.js 14 (App Router) | Server components for performance. Works with Capacitor for mobile. |
| Styling | Tailwind CSS + LN Design System tokens | Override Tailwind defaults with LN vars. Space Grotesk loaded via next/font. |
| State | Zustand | Lightweight. Offline queue state. Cart/POS state. |
| Data fetching | TanStack Query | Caching, background sync, optimistic updates for POS speed. |
| Charts | Recharts | Dashboard visualizations. Lightweight. |
| PWA | next-pwa | Offline capability. Service worker. Local cache for product catalog. |

### Mobile
| Layer | Technology | Reason |
|---|---|---|
| Wrapper | Capacitor 6 | Wraps Next.js build into native Android (and later iOS). One codebase. |
| Camera | @capacitor/camera | Barcode scanning for product lookup. |
| Notifications | @capacitor/push-notifications + FCM | Low-stock alerts. M-Pesa confirmation. Daily summary. |
| Storage | @capacitor/preferences | Offline sale queue. Local session cache. |
| Network | @capacitor/network | Detect offline → queue sales → sync on reconnect. |

### Infrastructure (prototype phase)
| Layer | Technology |
|---|---|
| Hosting | Localhost + ngrok (prototype). VPS (DigitalOcean) post-pilot. |
| Process manager | Supervisord (Django + Celery + Channels) |
| Reverse proxy | nginx (when moving to VPS) |
| Static files | Whitenoise (prototype). S3/Cloudflare (production). |
| Secrets | python-decouple + `.env` (never committed to git) |
| Version control | GitHub (private repo) |

---

## 2. Repository Structure

```
bizyango/
├── backend/                        # Django project
│   ├── bizyango/                   # Project config
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   ├── asgi.py                 # Channels entry point
│   │   └── celery.py
│   ├── apps/
│   │   ├── accounts/               # Users, roles, OTP auth
│   │   ├── business/               # Business profile, settings
│   │   ├── catalog/                # Products, categories, pricing
│   │   ├── transactions/           # The core transaction engine
│   │   ├── inventory/              # Stock levels, alerts, counts
│   │   ├── payments/               # M-Pesa integration, reconciliation
│   │   ├── reports/                # Dashboard data, summaries
│   │   └── notifications/          # Push, SMS, WhatsApp dispatch
│   ├── requirements/
│   │   ├── base.txt
│   │   ├── development.txt
│   │   └── production.txt
│   ├── manage.py
│   └── .env.example
├── frontend/                       # Next.js app
│   ├── app/
│   │   ├── (auth)/                 # Login, OTP verification
│   │   ├── (app)/
│   │   │   ├── dashboard/          # Owner INSIGHT MODE
│   │   │   ├── sell/               # Cashier SELL MODE
│   │   │   ├── stock/              # STOCK MODE
│   │   │   ├── reports/
│   │   │   ├── settings/
│   │   │   └── layout.tsx          # Left-rail nav (app layout)
│   │   └── layout.tsx              # Root layout
│   ├── components/
│   │   ├── ui/                     # LN Design System components
│   │   ├── sell/                   # POS-specific components
│   │   ├── stock/                  # Inventory components
│   │   └── dashboard/              # Chart and stat components
│   ├── lib/
│   │   ├── api.ts                  # Axios instance, interceptors
│   │   ├── auth.ts                 # JWT handling
│   │   └── offline-queue.ts        # Sale queuing when offline
│   ├── styles/
│   │   └── globals.css             # LN Design System CSS vars
│   ├── capacitor.config.ts
│   ├── next.config.js
│   └── package.json
├── android/                        # Capacitor Android project (generated)
├── ios/                            # Capacitor iOS project (generated, later)
├── docker-compose.yml              # Local dev: postgres + redis
└── README.md
```

---

## 3. Data Models

### accounts.User
```
id (UUID)
phone_number (unique, E.164 format)
name
role (OWNER | MANAGER | CASHIER)
business (FK → Business)
is_active
date_joined
last_login
```

### accounts.OTPToken
```
id
phone_number
token (6-digit, hashed)
created_at
expires_at (10 minutes)
is_used
attempts (max 3)
```

### business.Business
```
id (UUID)
name
type (DUKA | HARDWARE | BOUTIQUE | STATIONERY | PHARMACY | AGROVET | CUSTOM)
custom_type_name
mpesa_till_number
mpesa_paybill_number
mpesa_business_shortcode
owner (FK → User)
address
location_lat / location_lng
currency (default: KES)
timezone (default: Africa/Nairobi)
created_at
is_active

# Demo / subscription control
subscription_status (DEMO | ACTIVE | EXPIRED | SUSPENDED)  # default: DEMO
demo_started_at (datetime — set automatically on business creation)
demo_expires_at (datetime — demo_started_at + DEMO_PERIOD_DAYS, set on creation)
demo_period_days (int — default: 14, set per-business so you can extend for specific users)
subscribed_at (datetime, nullable — set when they convert to paid)
suspended_at (datetime, nullable)
suspension_reason (nullable)
```

### catalog.Category
```
id
business (FK)
name
description
is_active
```

### catalog.Product
```
id (UUID)
business (FK)
category (FK, nullable)
name
sku (auto-generated, editable)
barcode (nullable)
selling_price
cost_price (nullable — for margin calculation)
unit (piece | kg | litre | pack | custom)
current_stock (decimal — updated by transaction signals)
low_stock_threshold
track_stock (bool — some items may not need tracking)
image (nullable)
is_active
created_at
updated_at
```

### transactions.Transaction
```
id (UUID)
business (FK)
type (SALE | STOCK_IN | ADJUSTMENT | LOSS | DAMAGE | REFUND | TRANSFER)
reference_number (auto-generated, human-readable: BY-2026-0001)
total_amount
payment_method (CASH | MPESA | CREDIT | MIXED)
payment_status (PENDING | CONFIRMED | FAILED | DISPUTED)
mpesa_reference (nullable)
notes
created_by (FK → User)
created_at
is_voided
void_reason
void_by
```

### transactions.TransactionItem
```
id
transaction (FK)
product (FK)
quantity
unit_price (snapshot at time of sale — price may change later)
cost_price (snapshot)
subtotal
```

### inventory.StockMovement
```
id (UUID)
business (FK)
product (FK)
transaction (FK, nullable — for audit trail)
movement_type (SALE | RESTOCK | ADJUSTMENT | LOSS | DAMAGE | REFUND | COUNT)
quantity_change (positive or negative)
quantity_before
quantity_after
notes
created_by (FK → User)
created_at
```

### payments.MPesaTransaction
```
id (UUID)
business (FK)
transaction (FK, nullable — linked when matched)
mpesa_receipt_number (unique)
phone_number (sender)
amount
transaction_date
transaction_type (C2B | STK_PUSH | B2C)
is_matched (bool)
is_reconciled (bool)
raw_payload (JSONField — full Daraja response)
created_at
```

### payments.MPesaSTKRequest
```
id
business (FK)
transaction (FK)
checkout_request_id
merchant_request_id
phone_number
amount
status (PENDING | SUCCESS | FAILED | TIMEOUT)
result_code
result_desc
created_at
completed_at
```

---

## 4. API Endpoints

### Auth
```
POST   /api/v1/auth/otp/request/          # Send OTP to phone number
POST   /api/v1/auth/otp/verify/           # Verify OTP, return JWT pair
POST   /api/v1/auth/token/refresh/        # Refresh access token
POST   /api/v1/auth/logout/              # Blacklist refresh token
GET    /api/v1/auth/me/                  # Current user profile
```

### Business
```
POST   /api/v1/business/setup/           # Create business (onboarding step 1)
GET    /api/v1/business/                 # Get current business
PATCH  /api/v1/business/                 # Update business settings
GET    /api/v1/business/users/           # List staff
POST   /api/v1/business/invite/          # Send staff invite link
DELETE /api/v1/business/users/{id}/      # Remove staff member
```

### Catalog
```
GET    /api/v1/catalog/products/         # List products (search, filter, paginate)
POST   /api/v1/catalog/products/         # Create product
GET    /api/v1/catalog/products/{id}/    # Get single product
PATCH  /api/v1/catalog/products/{id}/    # Update product
DELETE /api/v1/catalog/products/{id}/    # Soft delete
POST   /api/v1/catalog/products/import/  # CSV bulk import
GET    /api/v1/catalog/categories/       # List categories
POST   /api/v1/catalog/categories/       # Create category
```

### Transactions
```
POST   /api/v1/transactions/sale/        # Record a sale
POST   /api/v1/transactions/stock-in/    # Add stock delivery
POST   /api/v1/transactions/adjustment/  # Manual stock adjustment
POST   /api/v1/transactions/loss/        # Log theft/damage/expiry
POST   /api/v1/transactions/refund/      # Process refund
GET    /api/v1/transactions/             # List transactions (filterable)
GET    /api/v1/transactions/{id}/        # Transaction detail
POST   /api/v1/transactions/{id}/void/   # Void a transaction
```

### Inventory
```
GET    /api/v1/inventory/                # Current stock levels (all products)
GET    /api/v1/inventory/low-stock/      # Products below threshold
GET    /api/v1/inventory/movements/      # Stock movement log
POST   /api/v1/inventory/count/          # Submit a stock count
```

### Payments
```
POST   /api/v1/payments/mpesa/stk-push/           # Initiate STK Push to customer
POST   /api/v1/payments/mpesa/callback/            # Daraja webhook (public, signed)
POST   /api/v1/payments/mpesa/c2b/confirmation/    # C2B confirmation webhook
POST   /api/v1/payments/mpesa/c2b/validation/      # C2B validation webhook
GET    /api/v1/payments/mpesa/transactions/         # List M-Pesa transactions
POST   /api/v1/payments/mpesa/reconcile/           # Trigger manual reconciliation
POST   /api/v1/payments/mpesa/import-statement/    # Upload M-Pesa PDF statement
```

### Reports
```
GET    /api/v1/reports/dashboard/        # Today's summary (revenue, txns, top products)
GET    /api/v1/reports/daily/            # Daily report (date param)
GET    /api/v1/reports/period/           # Date range report
GET    /api/v1/reports/products/         # Product performance
GET    /api/v1/reports/losses/           # Loss report by type/period
GET    /api/v1/reports/eod-summary/      # End-of-day summary (for WhatsApp dispatch)
```

### WebSocket
```
ws://  /ws/dashboard/                    # Live dashboard feed (owner)
ws://  /ws/pos/                          # POS sync + M-Pesa confirmation push
```

---

## 5. Security Plan

Security is non-negotiable even in prototype phase. Real business data and real M-Pesa transactions will be flowing through this system from day one.

### Authentication & Authorization
- [ ] JWT access tokens: 15-minute expiry. Refresh tokens: 7 days.
- [ ] Refresh token rotation: each use issues a new refresh token, old one is blacklisted.
- [ ] OTP tokens: 6-digit, hashed (not stored in plaintext), 10-minute expiry, max 3 attempts before lockout.
- [ ] Phone number rate limiting: max 3 OTP requests per phone number per hour.
- [ ] Role-based permissions enforced at the API view level (not just frontend):
  - OWNER: full access to all endpoints
  - MANAGER: all except billing, user management, business deletion
  - CASHIER: sell/, inventory read-only, own transaction history only
- [ ] Every API request validates that the resource belongs to the authenticated user's business (tenant isolation).

### Tenant Isolation
- [ ] Every model carries a `business` FK. Every queryset is filtered by `request.user.business`.
- [ ] Custom DRF permission class `IsSameBusiness` enforced on all viewsets.
- [ ] No cross-business data leakage is possible through any API endpoint.
- [ ] Business ID is never derived from URL or query param alone — always from the authenticated JWT.

### M-Pesa Webhook Security
- [ ] Daraja callback endpoint (`/payments/mpesa/callback/`) is public (Safaricom calls it).
- [ ] Request validated via Safaricom IP allowlist (published by Safaricom).
- [ ] Payload signature verification where Daraja supports it.
- [ ] Idempotency: `mpesa_receipt_number` is unique-constrained. Duplicate callbacks are silently discarded.
- [ ] Webhook processing is async (Celery task) — the callback endpoint returns 200 immediately.
- [ ] All raw Daraja payloads stored in `MPesaTransaction.raw_payload` for audit.

### Input Validation & Injection Prevention
- [ ] All inputs validated via DRF serializers with explicit field types and length limits.
- [ ] No raw SQL queries — ORM only.
- [ ] File upload validation for CSV import and M-Pesa PDF: MIME type + extension check + size limit (5MB).
- [ ] Product names, notes, and all free-text fields sanitized (strip HTML, limit length).
- [ ] Phone number validated to E.164 format before any OTP dispatch.

### API Security
- [ ] HTTPS enforced (ngrok provides this in prototype; nginx + Let's Encrypt in production).
- [ ] CORS: only the Next.js frontend origin is whitelisted. No wildcard `*`.
- [ ] `ALLOWED_HOSTS` locked down — never `*` even in development on deployed instances.
- [ ] Rate limiting via `django-ratelimit`:
  - OTP request: 3 per hour per phone
  - Login attempts: 10 per hour per IP
  - Sale recording: 60 per minute per user (prevents POS runaway loops)
  - General API: 300 requests per minute per authenticated user
- [ ] `X-Content-Type-Options: nosniff` header on all responses.
- [ ] `X-Frame-Options: DENY` header.
- [ ] Django `SECRET_KEY` in environment variable, never in source.

### Data Security
- [ ] `DEBUG = False` in all non-local environments.
- [ ] Sensitive fields (cost prices, business financials) excluded from cashier-role API responses.
- [ ] No PII logged in application logs (no phone numbers, no M-Pesa details in plaintext logs).
- [ ] Database backups: daily automated backup to separate location (even in prototype phase — this is real business data).
- [ ] `.env` file never committed to git. `.gitignore` includes `.env`, `*.env`, `local_settings.py`.

### Frontend Security
- [ ] JWT stored in `httpOnly` cookies, not `localStorage`. XSS cannot steal tokens.
- [ ] CSRF token required for all non-GET requests (Django's built-in protection).
- [ ] API base URL in environment variable, not hardcoded.
- [ ] No sensitive data (prices, M-Pesa references) in browser URL params.
- [ ] Content Security Policy header configured.

### Infrastructure (Prototype)
- [ ] ngrok authtoken configured. Static domain used (not random subdomain).
- [ ] ngrok inspect dashboard (`localhost:4040`) is NOT exposed externally.
- [ ] Laptop firewall: only port 443 (ngrok tunnel) and local ports accessible.
- [ ] Redis not exposed externally — localhost only.
- [ ] PostgreSQL not exposed externally — localhost only (or Docker network only).

---

## 6. Build Phases — Detailed

### Phase 0 — Project Skeleton (Session 1)
**Goal:** Both servers running, talking to each other, Capacitor building to Android.

- [ ] `django-admin startproject bizyango backend/`
- [ ] Create all Django apps: `accounts`, `business`, `catalog`, `transactions`, `inventory`, `payments`, `reports`, `notifications`
- [ ] Settings split: `base.py`, `development.py`, `production.py`
- [ ] PostgreSQL configured via Docker Compose
- [ ] Redis configured via Docker Compose
- [ ] `django-cors-headers` configured for Next.js origin
- [ ] `djangorestframework`, `djangorestframework-simplejwt` installed
- [ ] `django-channels` installed and configured with Redis channel layer
- [ ] `npx create-next-app@latest frontend --typescript --tailwind --app`
- [ ] LN Design System CSS vars injected into `globals.css`
- [ ] Space Grotesk + JetBrains Mono loaded via `next/font/google`
- [ ] Dark mode as default (`class` strategy, `html` element)
- [ ] Axios instance configured with JWT interceptors and refresh logic
- [ ] `npx cap init` in frontend directory
- [ ] Android platform added (`npx cap add android`)
- [ ] First `npx cap build` verified on Android emulator
- [ ] ngrok tunnel script configured
- [ ] GitHub repo initialized, `.gitignore` set, secrets excluded
- [ ] `README.md` with local setup instructions

**Deliverable:** `http://localhost:3000` loads the LN-themed shell. Android emulator loads the same app. Django API returns 200 on `/api/v1/health/`.

---

### Phase 1 — Auth & Business Setup (Session 1–2)
**Goal:** A new user can register with their phone, verify OTP, set up their business, and add their first 5 products.

- [ ] `OTPToken` model + `User` model (custom AbstractBaseUser)
- [ ] Africa's Talking SDK integrated for OTP SMS dispatch
- [ ] OTP request endpoint with rate limiting
- [ ] OTP verify endpoint returning JWT pair
- [ ] Token refresh endpoint
- [ ] JWT middleware for all subsequent requests
- [ ] Role enum: OWNER, MANAGER, CASHIER
- [ ] `IsSameBusiness` permission class
- [ ] Business setup wizard (3 screens):
  - Screen 1: Business name + type selector (Duka / Hardware / Boutique / Stationery / Custom)
  - Screen 2: M-Pesa till or paybill number
  - Screen 3: "Add your 5 most-sold items" (NOT "enter all your stock")
- [ ] Product creation form: name, selling price, current quantity, low-stock threshold
- [ ] CSV import endpoint + frontend file upload for bulk catalog
- [ ] Staff invite: owner generates a one-time invite link → cashier opens it → registers with their phone → auto-joins the business

**Security checkpoints:**
- OTP rate limiting active
- Role permissions tested for all three roles
- Tenant isolation verified (user cannot access another business's data)

---

### Phase 2 — Transaction Engine: SELL MODE (Session 2–3)
**Goal:** A cashier can record a complete sale in under 30 seconds.

- [ ] `Transaction` + `TransactionItem` models
- [ ] `StockMovement` model
- [ ] Django signals: on `Transaction` save → auto-create `StockMovement` → update `Product.current_stock`
- [ ] `reference_number` auto-generation (BY-2026-XXXX format)
- [ ] SELL MODE UI:
  - Product search (name or SKU)
  - Tap to add to cart
  - Quantity adjustment
  - Payment method selector (Cash / M-Pesa / Mixed)
  - Confirm sale button
  - Success screen with reference number
- [ ] Offline queue: if no internet, sale is stored in `@capacitor/preferences` and synced on reconnect
- [ ] Receipt generation: shareable text receipt via WhatsApp (wa.me link with pre-filled text)
- [ ] Transaction list view (owner/manager can see all; cashier sees own only)
- [ ] Void transaction (owner only, requires reason)

---

### Phase 3 — STOCK MODE & Inventory (Session 3–4)
**Goal:** Owner can see real-time stock levels and log any stock movement.
**Status: ✅ Complete — see CHANGES.md, Session 5.**

- [x] Stock levels view: all products with current quantity, status (OK / LOW / OUT)
- [x] Low-stock badge: any product below threshold highlighted in red
- [x] Add delivery (STOCK_IN): select product, enter quantity received, supplier name (optional)
- [x] Log loss: select product, quantity, loss type (THEFT / DAMAGE / EXPIRY / OTHER), notes
- [x] Manual adjustment: correct a stock count discrepancy, enter reason
- [x] Stock count sheet: list all products, enter physical count, system calculates discrepancies
- [x] Push notification when a product hits low-stock threshold (Capacitor FCM)
- [x] Stock movement log: full audit trail per product

---

### Phase 4 — M-Pesa Integration (Session 4–5)
**Goal:** M-Pesa payments are confirmed and matched to sales automatically.

- [ ] Daraja Sandbox credentials configured
- [ ] STK Push endpoint: owner triggers payment request to customer's phone from POS
- [ ] STK Push callback webhook: Celery task processes result, updates `MPesaSTKRequest`
- [ ] WebSocket push: on STK Push success, POS screen updates in real-time without refresh
- [ ] C2B webhook (till number): customer pays, system receives confirmation
- [ ] Auto-match: incoming M-Pesa receipts matched to open `Transaction` by amount + time window (±5 minutes)
- [ ] Unmatched M-Pesa log: transactions received but not yet linked to a sale
- [ ] M-Pesa PDF statement import (reuse LifeApp parser logic)
- [ ] Reconciliation view: matched, unmatched, flagged discrepancies
- [ ] Safaricom IP allowlist enforced on callback endpoints

---

### Phase 5 — Owner Dashboard & Reports (Session 5–6)
**Goal:** Owner opens the app and immediately knows how today is going.
**Status: ✅ Complete — see PHASE5_HANDOFF.md for what was finished this session.**

- [x] Dashboard WebSocket feed: live revenue counter, live transaction count
- [x] Today's stats: revenue, transaction count, average transaction value, cash vs M-Pesa split
- [x] Yesterday comparison: +/- delta on revenue
- [x] Top 5 products by sales today
- [x] Low-stock alert strip (products needing restock)
- [x] End-of-day summary — manual dispatch via WhatsApp share sheet is built
      (`GET /reports/eod-summary/` + share button on the Daily report tab).
      **Automatic 9pm trigger not built** — needs a Celery beat task; nothing
      currently schedules it. See PHASE5_HANDOFF.md.
- [x] Daily report: date-filterable, full breakdown
- [x] Loss report: by type, by period, by employee
- [x] Product performance report: revenue contribution, units sold, margin

---

### Phase 6 — Prototype Polish & Test User Deployment (Session 6–7)
**Goal:** 5–10 test users can be onboarded and use the app daily on their phones.

- [ ] Progressive onboarding flow reviewed and tightened (time-to-first-sale under 10 minutes)
- [ ] Error states: every form has proper validation messages in Kiswahili
- [ ] Empty states: first-time views have clear CTAs, not blank screens
- [ ] Loading states: skeleton screens on dashboard, not spinners on everything
- [ ] Offline indicator: app shows banner when offline, queued sales shown
- [ ] Capacitor Android APK built and signed (debug cert for prototype)
- [ ] APK distributed via WhatsApp to test users (direct install, no Play Store yet)
- [ ] ngrok static domain configured. Django + Celery + Channels running via Supervisord.
- [ ] Test user onboarding: founder visits each user, installs APK, walks through setup
- [ ] WhatsApp support group created for test users
- [ ] Crash reporting: Sentry integrated (free tier)
- [ ] Basic analytics: who's using what, which features get used, which don't

---

## 7. Security Audit Checklist (Pre-Deployment)

Run this before giving any test user access to the system.

### Django
- [ ] `DEBUG = False`
- [ ] `SECRET_KEY` from environment, not settings file
- [ ] `ALLOWED_HOSTS` set to ngrok domain only
- [ ] `SECURE_BROWSER_XSS_FILTER = True`
- [ ] `SECURE_CONTENT_TYPE_NOSNIFF = True`
- [ ] `X_FRAME_OPTIONS = 'DENY'`
- [ ] Database user has only SELECT/INSERT/UPDATE/DELETE — no DDL permissions in production
- [ ] No `print()` statements containing user data or tokens in production code
- [ ] Django admin disabled or moved to non-default URL

### API
- [ ] All endpoints require authentication except: OTP request, OTP verify, Daraja webhooks
- [ ] Daraja webhook endpoints validate source IP
- [ ] Rate limiting active on OTP, login, and general API
- [ ] File uploads: type validated, size limited, stored outside web root
- [ ] No stack traces in API error responses (only in development)

### Frontend
- [ ] JWT in httpOnly cookie, not localStorage
- [ ] No API keys or secrets in Next.js client-side code
- [ ] Environment variables with `NEXT_PUBLIC_` prefix are genuinely non-sensitive

### Penetration test (manual, pre-pilot)
- [ ] Attempt to access another business's products via direct ID manipulation
- [ ] Attempt to escalate cashier role to owner via API
- [ ] Attempt to submit a negative quantity sale
- [ ] Attempt to submit an OTP more than 3 times
- [ ] Attempt to call Daraja callback endpoint with fake payload
- [ ] Attempt XSS via product name field

---

## 8. Non-Functional Requirements

| Requirement | Target | Notes |
|---|---|---|
| Time to first sale | < 10 minutes | From fresh install to first recorded transaction |
| POS transaction record time | < 30 seconds | Tap item → confirm sale → receipt |
| Dashboard load time | < 2 seconds | On 3G connection |
| Offline capability | Core POS only | Sales queue offline, sync on reconnect |
| Concurrent users | 1–3 per business | Prototype target. Scale later. |
| Uptime (prototype) | Best effort | ngrok + laptop. Not SLA-bound. |
| Data retention | All data kept | No deletion of transaction records ever |
| Audit trail | Complete | Every stock movement traceable to a user and timestamp |

---

## 9. Demo Control System

### Philosophy
The demo is time-limited to prevent indefinite free use. Degradation is graceful — never hostile. The user keeps their data and read access; they just can't write new transactions until they subscribe. All enforcement is backend-only. The frontend reflects state; it never enforces it.

### Timeline
| Day | State | What happens |
|---|---|---|
| 1–10 | DEMO, silent | Full access. No mention of expiry. Let them get dependent on it. |
| 11–13 | DEMO, warning | Soft banner on every screen: "Biashara yako ya majaribio inaisha siku {N}. Wasiliana na Lewis: 07XX XXX XXX" |
| 14 | EXPIRED | App goes read-only. Dashboard and reports still work. All write operations blocked. |
| 14+ | EXPIRED, locked | Banner becomes persistent full-screen overlay on the dashboard with a WhatsApp CTA to you. |

### Backend implementation

**Model method on `Business`:**
```python
def is_demo_expired(self):
    if self.subscription_status == 'ACTIVE':
        return False
    if self.subscription_status == 'EXPIRED':
        return True
    # DEMO state — check clock
    return timezone.now() >= self.demo_expires_at

def days_remaining(self):
    if self.subscription_status != 'DEMO':
        return None
    delta = self.demo_expires_at - timezone.now()
    return max(0, delta.days)
```

**Custom DRF permission class — add to `IsSameBusiness`:**
```python
class IsNotExpired(BasePermission):
    """
    Blocks all write operations (POST, PATCH, PUT, DELETE) for expired demos.
    Read operations (GET) are always allowed — users keep access to their data.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:  # GET, HEAD, OPTIONS
            return True
        business = request.user.business
        if business.is_demo_expired():
            raise PermissionDenied(
                detail={
                    "error": "demo_expired",
                    "message": "Kipindi chako cha majaribio kimeisha. Wasiliana na Lewis kupata usajili.",
                    "whatsapp": "https://wa.me/254XXXXXXXXX"
                }
            )
        return True
```

Apply both `IsSameBusiness` and `IsNotExpired` to all viewsets:
```python
permission_classes = [IsAuthenticated, IsSameBusiness, IsNotExpired]
```

**Celery beat task — runs daily at midnight:**
```python
@shared_task
def check_demo_expirations():
    expired = Business.objects.filter(
        subscription_status='DEMO',
        demo_expires_at__lte=timezone.now()
    )
    expired.update(subscription_status='EXPIRED')
    # Optional: send WhatsApp notification to owner on expiry day
```

**Admin override — you can extend a specific user's demo:**
```python
# In Django admin or a management command:
business.demo_expires_at = timezone.now() + timedelta(days=7)
business.save()
```

### Frontend implementation

**API response includes demo state on every authenticated request** (add to the `/api/v1/auth/me/` response):
```json
{
  "user": { ... },
  "business": {
    "subscription_status": "DEMO",
    "days_remaining": 4,
    "demo_expires_at": "2026-07-10T00:00:00Z"
  }
}
```

**Global state (Zustand store):** `useDemoStore` holds `subscription_status` and `days_remaining`. Updated on every page load.

**Warning banner component:** Renders on all app pages when `days_remaining <= 3`. Dismissible per session, reappears next login.

**Expired overlay:** When `subscription_status === 'EXPIRED'`, a full-screen non-dismissible overlay sits above the dashboard. Shows summary of their data, lock icon, and WhatsApp button. They can still navigate to reports (read) but cannot dismiss the overlay on write-mode screens.

**Write buttons:** When expired, POST/PATCH/DELETE buttons are visually disabled and show a lock icon. Clicking them shows a toast: "Kipindi cha majaribio kimeisha." — even before the API call is made, for UX speed.

### Security notes
- Expiry is enforced at the API permission layer. Disabling the frontend lock does nothing.
- `demo_expires_at` is server-set on business creation. It is never accepted from the client.
- Demo extension (for specific test users) is done manually in Django admin or via a management command — never via a public API endpoint.
- `subscription_status` is never writeable via the API. Only internal code and Django admin can change it.

---

## 10. Key Design Decisions & Rationale

| Decision | Rationale |
|---|---|
| Progressive catalog onboarding (not full stock count) | Field research: one established shop owner declined the prototype specifically because full stock entry felt too painful. Start with 5 items, grow the catalog over time. |
| Stock level derived from transaction history | Accuracy builds over time as more transactions are recorded. No artificial "opening stock" pressure. |
| WhatsApp for receipts and notifications | 100% of target users already have WhatsApp. No app download required to receive a receipt as a customer. |
| Kiswahili-first copy | Field interviews conducted in Kiswahili. Most respondents were more comfortable in Kiswahili. All UI copy defaults to Kiswahili with English fallback. |
| Dark-first UI | LN Design System mandate. Also: shop environments often have mixed lighting; dark UI is less glaring on a phone screen behind a counter. |
| Django as backend despite Next.js frontend | Separation of concerns. Django is the data and business logic layer. Next.js is the presentation layer. Capacitor is the mobile wrapper. Three clearly bounded responsibilities. |
| No subscription billing in prototype | The field data showed zero deposit conversions. The product needs to prove itself first. Billing adds complexity and friction before trust is established. |
| Time-limited demo with graceful degradation | Prevents indefinite free use. Read-only expiry (not full lockout) keeps the user's data accessible and avoids hostility — they can still see their history, they just can't record new sales. Enforced at API level, not frontend. |

---

## 11. Post-Prototype Roadmap (Not in Scope Yet)

These are explicitly deferred until the prototype has real usage data:

- Subscription billing via M-Pesa
- Debt / credit customer tracking
- Supplier management
- Multi-branch support
- Advanced loss analytics
- Play Store / App Store submission
- VPS deployment (move off ngrok)
- Marketing website
- CompanyOS AI team activation
- Payroll module
- KRA iTax integration

---

## 12. Session Continuity Protocol

Each build session should begin by uploading the current state of the codebase. Minimum files to bring:

| File | Why |
|---|---|
| `backend/apps/*/models.py` | Data model state |
| `backend/apps/*/serializers.py` | API contract |
| `backend/apps/*/views.py` | Endpoint logic |
| `backend/bizyango/settings/base.py` | Config state |
| `backend/requirements/base.txt` | Dependency state |
| `frontend/app/**/*.tsx` (changed files) | UI state |
| `frontend/lib/api.ts` | API client state |
| `capacitor.config.ts` | Mobile config |

Deliverables from each session: zip patch of changed files only, with a `CHANGES.md` listing what was added, modified, or fixed.

---

## 13. First Session Starting Point

**Session 1 goal:** Phase 0 complete. Both servers running. Android emulator showing the LN-themed app shell.

**Commands to run first:**
```bash
# Backend
python -m django startproject bizyango backend
cd backend
pip install django djangorestframework djangorestframework-simplejwt django-cors-headers channels channels-redis celery django-environ

# Frontend
npx create-next-app@latest frontend --typescript --tailwind --app --src-dir

# Capacitor (from frontend/)
npm install @capacitor/core @capacitor/cli
npm install @capacitor/android @capacitor/camera @capacitor/push-notifications @capacitor/preferences @capacitor/network
npx cap init BizYangu co.bizyango.app
npx cap add android
```

**First thing to build:** The Django health check endpoint and the Next.js root layout with LN Design System tokens. Verify they talk to each other. Then Capacitor build on Android. Foundation before features.

---

*BizYangu Build Plan v1.0 — Lewis Nyakundi — June 2026*
*This document evolves with the project. Update version number on each significant revision.*
