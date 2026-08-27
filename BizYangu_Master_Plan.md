# BizYangu — Master Plan
**Single source of truth.** Consolidates `BizYangu_Build_Plan_v1.md`,
`BizYangu_Build_Plan_v2.md`, `v2 buildplan.md` (a hand-annotated scratch
copy of v2, fully absorbed into v3's restructuring), `BizYangu_Build_Plan_v3.md`,
and `BizYangu_Deployment_Checklist.md` into one document.
**Written:** August 2026, from the state captured in the `bizyangu-001` handoff package.

The four prior build-plan files and the deployment checklist should be
considered superseded by this document. Keep them in the repo under
`archive/` for history if you want the narrative of how the plan evolved —
don't delete them, but don't edit them either. Update this file going forward.

---

## 0. What BizYangu is

A mobile-first business management platform for Kenyan SMEs — dukas,
hardware shops, boutiques, stationery shops, salons, and similar small
businesses. Replaces notebooks, manual M-Pesa checks, and guesswork with
real-time sales tracking, stock visibility, and payment reconciliation.

**Design authority:** LN Design System v1.0 — dark-first (`#0A0A0A` base,
`#00E5C4` teal accent, `#FF4D6D` error), Space Grotesk + JetBrains Mono,
12-column grid, base-8 spacing, Kiswahili-first copy with English fallback.

**Stack:** Django 5 + DRF + Channels (backend) · Next.js 14 App Router +
Tailwind + Zustand + TanStack Query (frontend) · Capacitor 6 (Android
wrapper) · PostgreSQL + Redis + Celery · Safaricom Daraja (M-Pesa) ·
Africa's Talking (OTP/SMS). Full stack rationale table is in the archived
v1 if you need the "why" for any of these — not repeated here since none
of it is being reconsidered.

---

## 1. Where things actually stand

| Phase | What | Status |
|---|---|---|
| 0 | Skeleton | ✅ Complete |
| 1 | Auth & Business Setup | ✅ Complete |
| 2 | SELL MODE | ✅ Complete (barcode scan not wired — `@capacitor/camera` installed, unused) |
| 3 | Stock/Inventory | ✅ Complete |
| 4 | M-Pesa | ✅ Complete except statement import (deferred — waiting on LifeApp parser) |
| 5 | Dashboard & Reports | ✅ Complete except automatic 9pm EOD trigger (manual WhatsApp dispatch works; no Celery beat task) |
| 5.5 | Settings + Staff Invite | ✅ Complete — business profile edit, staff list/invite/remove, `/join` acceptance flow |
| 5.6 | Security/hygiene pass | ✅ Complete — general API rate limiting, Sentry initialized, admin URL moved off default path |
| 6 | Sessions/JWT/Redis/N+1 audit | ⬜ Not started |
| 6.5 | Notification abstraction layer (OTP/SMS/WhatsApp/email) | ⬜ Not started — see §3.2 |
| 7 | Reports: growth & profit graphs | ⬜ Not started |
| 8 | Knowledge Base Curation (taxonomy) | ✅ **Complete, ahead of plan** — see §3.1 note below |
| 9 | Sell-without-inventory + progressive catalog | ⬜ Not started (taxonomy it depends on is ready) |
| 10 | Demo-driven taxonomy refinement | ⬜ Not started |
| 11 | Perishability tracking | ⬜ Not started |
| 12 | Creditor UI / customer ledger | ⬜ Not started |
| 13 | Cross-business sub-niche detection | ⬜ Not started (data-gated) |
| 14 | More settings | ⬜ Not started (waiting on concrete list) |

**Still open from earlier phases, unchanged:**
- Automatic 9pm EOD WhatsApp trigger (needs Celery beat task + a decision on unattended send mechanism)
- M-Pesa PDF statement import
- Barcode scanning
- Partial-refund UI (backend supports it, no button calls it yet)

None of these block anything below.

### 3.1 Note on Phase 8 status
The numbered phase list below was written as a forward plan, but the
`knowledge/` directory contents (per `knowledge/README.md` in the handoff
package) show Phase 8 is **already built**: 9 business-type taxonomies
(hardware, bar, kiosk, clothing_store, wholesale, salon_barbershop,
cereals_grains, auto_spares, garage), all 107 brand placeholders filled and
applied, structural validation passed (no dangling references). What's
explicitly **not yet done**: none of this JSON is wired into `backend/`
yet — that wiring is Phase 9 work, not a Phase 8 gap. Content accuracy
(brand names, colloquial units like debe/gorogoro/gunia) is flagged as
unreviewed against real Kenyan market reality — worth a pass before Phase
9 ships it into onboarding.

### 3.2 Note on Phase 6.5 (notification layer) — why it exists and how it got scoped
Africa's Talking (AT) is BizYangu's current, working OTP/SMS provider. It
was never actually broken — AT's published Kenya pricing (verified against
their own 2025 pricing sheet) is KES 0.8/SMS at pilot volume and KES 8,700
one-off for a Safaricom-only Sender ID (KES 14,100 if bundled with Airtel —
the "KES 14K" figure that originally made AT look like a blocker was the
bundled price, not the Safaricom-only price BizYangu actually needs).

The reason to move is **architectural, not a fire**: relying on a single
SMS vendor for something as load-bearing as login OTP is a single point of
failure, and other Kenyan providers turned out to be genuinely cheaper at
pilot volume once real pricing sheets (not marketing pages) were checked:

| Provider | Verified pilot-volume rate | Sender ID | Source |
|---|---|---|---|
| Africa's Talking | KES 0.8/SMS (0–19,999/mo tier) | KES 8,700 one-off (Safaricom only) | AT's own 2025 pricing PDF |
| MobiWave | KES 0.35/SMS (1–50,000/mo tier) | Included, no separate fee shown | MobiWave's own pricing page |
| eSMS Africa | KES 1.08/SMS (KES 129–129,420 spend tier) | Included ("Custom SenderID" in Basic tier) | eSMS Africa's own pricing page |

Note the trap every "cheapest SMS in Kenya" blog post falls into: headline
rates (KES 0.15–0.25) are top-volume tiers, irrelevant at pilot scale. At
BizYangu's actual pilot volume, MobiWave is cheapest, AT is mid, and eSMS
Africa — despite the lowest *headline* number anywhere — is actually the
most expensive of the three until spend crosses ~KES 129,500/month.

**Robase** (`robase.dev`) was evaluated as a possible drop-in — a
multi-provider OTP router with automatic failover — but it prices in
Nigerian Naira with no confirmed Kenya coverage or rates, and using it
would mean trusting a third party's routing/failover logic for OTP
delivery with no visibility into which underlying carrier it actually
used. Decision: don't adopt Robase as a vendor — build the equivalent
routing/failover layer in-house instead, so BizYangu owns the failover
logic, the provider list, and the delivery data. See Phase 6.5 for the
resulting design.

**No provider has been dropped.** AT stays wired in as-is; this phase adds
alternatives behind an interface rather than ripping AT out first.

---

## 2. Cross-cutting principles

Constraints that apply across several phases below — get these wrong early
and it costs more later than building them in from the start.

### 2.1 Service businesses are first-class, not an edge case
Salons, barbershops, consultancies, repair shops — no physical stock.
Touches:
- **Catalog model:** `has_inventory: bool` (or equivalent) on Product, so
  stock fields (`current_stock`, `low_stock_threshold`, `unit`) are
  genuinely optional — not zero-defaulted in a way that triggers false
  "out of stock" alerts.
- **Onboarding presets:** service-type entries alongside physical-goods
  presets from day one.
- **Reports:** "top products by units sold" needs a service-shaped
  equivalent ("top services by revenue/bookings"). Loss/perishability
  reports should cleanly not apply, not show zeros.
- **Sell-without-inventory (Phase 9):** for a service business this is the
  permanent, first-class path — not a temporary bridge to a stock count.

### 2.2 Progressive onboarding is continuous, not one-time setup
Businesses start operating within minutes; inventory grows organically
through daily use. Sales always take priority over inventory completeness
— selling must never stop for a missing product. Two-stage adaptive
onboarding:

- **Stage 1 (Phase 9, build now against the Phase 8 taxonomy):** curated
  category/item suggestions per business type, not a flat preset list.
  Instrument from day one — log keep/delete/edit on suggested items, log
  every custom item added — zero behavioral effect now, this is the data
  Stage 2 needs later.
- **Stage 2 (Phase 13, later, data-gated):** sub-niche detection within a
  declared type via co-occurrence of custom items across businesses of
  that type — never a trained model, never a silent guess. New signups in
  a type with an established sub-tag get one soft follow-up question
  instead. Gate: don't build until there's a real distribution of custom
  items across a meaningful cohort (threshold TBD from real data).
- **Consent:** disclosed in terms of service / privacy policy that
  aggregated cross-business product data improves suggestions for others —
  don't forget this before Phase 13 ships.

### 2.3 The taxonomy hierarchy (from Phase 8, referenced by Phase 9+)
```
Business Type → Category → Subcategory → Common Item Names → Common Brands → Units
```
Example: `Hardware → Paint → Interior/Emulsion Paint → "Emulsion Paint" → Crown, Basco, Duracoat → 4L/20L, Bucket`

Service types use the same structure with no brand/unit slot:
`Salon → Hair Services → Cut / Color / Treatment → (no brand, no unit — priced per service)`

**What the knowledge base stores:** structure and vocabulary (types,
categories, subcategories, common names, brands, units).
**What it does NOT store:** actual products — those belong to each
business, seeded from and suggested against the taxonomy, never
pre-populated wholesale.

Two speeds of "smart," don't conflate them:
- **Within-business suggestion (fast, no gate):** once a business has 2+
  items in a taxonomy category, suggest that category's other common
  brands/names on next add — tap-to-accept, never auto-added. Ships as
  part of Phase 9.
- **Cross-business sub-niche detection (slow, data-gated):** Phase 13, see §2.2.

### 2.4 E-commerce/B2B marketplace — separate initiative, not a phase
Deliberately excluded from the numbered phases. When it's time: own
planning session starting with the trust/dispute/fund-flow model before
any schema work. **Regulatory flag, unresolved:** BizYangu orchestrating
the transaction while money moves M-Pesa-to-M-Pesa directly between
businesses (vs. BizYangu holding funds, which is money-transmitter/PSP
territory under the National Payment System Act) needs real input from
someone who knows Kenyan fintech regulation before it's decided either
way. Framed as B2B-first, Duka-owner-to-customer commerce as its own
product identity. No further scoping until that dedicated session happens.

---

## 3. Phases 6 onward — detail

### Phase 6 — Sessions, JWT, Redis, N+1 audit
**Goal:** confirm the infrastructure underneath everything else is solid
before building more on top of it. No product decisions required — a
"does what we already built work correctly" pass.

- [ ] Trace every list/detail endpoint for missing `select_related` /
      `prefetch_related` — reports, transactions, catalog, staff list are
      highest-traffic candidates
- [ ] Confirm refresh-token rotation is actually hitting the blacklist
      (verify the blacklist app is installed and rotation is observably
      working, not just configured in `SIMPLE_JWT`)
- [ ] Confirm what's actually running Redis today vs. SQLite/in-memory
      fallback in dev — Channels layer, cache backend, Celery broker may
      currently be three different things by accident
- [ ] Session/cookie lifetime sanity check against JWT lifetimes (15min
      access / 7day refresh) — confirm the frontend refresh flow exercises
      this correctly under real network conditions (flaky connections,
      backgrounded app)
- [ ] Document findings — this phase produces a written audit + fixes, not new UI

---

### Phase 6.5 — Notification abstraction layer (OTP, SMS, WhatsApp, email)
**Goal:** decouple `apps/accounts` (and anywhere else that sends an
OTP, receipt, or alert) from any single vendor's SDK. One interface,
swappable providers, per-channel routing with failover — owned by
BizYangu, not rented from a third party. See §3.2 for how this got
scoped and the pricing that informed it.

**In scope for this phase:** SMS channel only, with two real adapters
(AT, MobiWave) wired end-to-end. WhatsApp and email are designed for in
the interface but not built yet — see "Explicitly deferred" below.

**Design**

```
                     NotificationService (interface)
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                     │
   OTPChannel           BroadcastChannel      (future: push)
   (verification,       (receipts, low-stock
    login-blocking)      alerts, non-blocking)
        │                    │
   ┌────┴─────┬──────────┐   │
   │          │          │   │
  SMS      WhatsApp    Email │
   │          │          │   │
 ┌─┴──┐   (Phase 9.5+  (Phase 9.5+
 │    │    or later,    or later,
 AT  MobiWave  not      not
     (Phase   this      this
      6.5)    phase)    phase)
```

- **Provider interface, not provider-specific code anywhere else in the
  app.** Every adapter implements the same tiny contract:
  `send(to, message, **kwargs) -> DeliveryResult(success,
  provider_message_id, error, provider_name)`. `apps/accounts/services.py`'s
  `send_otp_sms()` calls `notification_service.send_otp(phone, code)` —
  it must not import `africastalking` or any vendor SDK directly.
  Today it almost certainly does; that direct coupling is the thing
  this phase removes.
- **Routing + failover lives in the service layer, once — never
  duplicated per adapter.** Config-driven priority list per channel,
  e.g. `SMS_PROVIDER_PRIORITY = ['mobiwave', 'africastalking']`. On
  failure (timeout, non-2xx, provider-reported delivery failure), fall
  through to the next provider in the list before giving up. Adapters
  stay dumb — they only know how to send and how to report back
  success/failure, not what to do about failure.
- **Provider selection lives in Django settings / env, not hardcoded.**
  Swapping which provider is primary, or adding a third, is a config
  change — not a code change in `apps/accounts`.
- **Log every send attempt: provider used, success/failure, latency,
  cost if known.** Per-business or aggregate. This is what actually
  lets BizYangu compare AT vs MobiWave vs a future provider on real
  delivery data instead of trusting anyone's marketing page — including
  this document's own pricing table above, which will go stale.
- **OTP failure UX:** if every provider in the SMS priority list fails
  for a given send, surface a clear "SMS delivery is currently
  unavailable" error rather than a generic 500 — this is a login-blocking
  path, the failure mode matters as much as the happy path.

**Tasks**
- [ ] Define `NotificationService` interface + `DeliveryResult` dataclass in `apps/notifications`
- [ ] Extract existing AT integration out of `apps/accounts/services.py` into an `AfricasTalkingAdapter` implementing the interface — behavior unchanged, just moved behind the interface
- [ ] Build `MobiWaveAdapter` against MobiWave's real API docs (get these directly from MobiWave — the pricing page doesn't cover API shape) — confirm Sender ID processing timeline and any hidden requirements (their shortcode products list a "1 week waiting period + authorisation letter"; confirm whether Sender ID has the same requirements before assuming it's instant)
- [ ] `SMS_PROVIDER_PRIORITY` setting + failover logic in the service layer
- [ ] Per-send delivery logging (provider, success/failure, latency) — a model or at minimum structured logging queryable later
- [ ] Swap `send_otp_sms()` and any other direct AT call sites to go through `NotificationService`
- [ ] `DEV_OTP_BYPASS` continues to short-circuit the whole service in dev — no change to that behavior
- [ ] One real end-to-end OTP test against each adapter (AT and MobiWave) with a real Kenyan phone number before this phase is considered done
- [ ] Update `backend/.env.example` with MobiWave credential placeholders alongside the existing AT ones

**Explicitly deferred, not in this phase:**
- WhatsApp as an OTP/notification channel — interface should not preclude it, but no adapter built now
- Email as a channel — same
- eSMS Africa adapter — documented as a candidate (§3.2) but not built; add only if AT+MobiWave prove insufficient, or if MobiWave's live API/Sender ID process turns out worse than its pricing page suggests
- Cost-based automatic provider selection (routing to whichever is cheapest per message) — priority-list failover only for now; cost optimization is a later refinement once there's real delivery data to optimize against
- Migrating existing WhatsApp receipt-sending (already built, per Phase 5) into this abstraction — that's a working feature today; leave it alone unless it starts using the same interface makes sense later, don't disrupt it to fit this phase's timeline

---

### Phase 7 — Reports: growth & profit graphs
**Goal:** turn existing daily/period aggregation into visual trend data.
Cheapest phase on the list — mostly frontend, `recharts` already a
dependency. No dependency on Phase 8/9 — can run in parallel.

- [ ] Revenue-over-time line chart (reuses `/reports/period/`'s `daily_breakdown`)
- [ ] Profit/margin trend (check whether this needs a new endpoint or a
      reshape of `/reports/products/`)
- [ ] Period-over-period growth indicator (this month vs. last, this week vs. last)
- [ ] Visual treatment for service-vs-goods businesses (§2.1) — a service
      business's growth chart shouldn't reference stock/margin concepts
      that don't apply

---

### Phase 8 — Knowledge Base Curation ✅ Complete
**Goal:** build the taxonomy (§2.3) before any onboarding or
inventory-growth feature depends on it. Produces version-controlled JSON,
not app code.

- [x] 9 business types curated for the first cohort: hardware, bar, kiosk,
      clothing_store, wholesale, salon_barbershop, cereals_grains,
      auto_spares, garage
- [x] Per type: categories, subcategories where useful, common brands and
      units at category/subcategory level
- [x] Service-type templates included (salon_barbershop, garage — no
      brand/unit on services; salon also has a `retail_addon` block for
      physical products it sells)
- [x] Stored as version-controlled JSON in `knowledge/` — no
      `products.json`; products are created by businesses, never
      pre-populated
- [x] All 107 brand placeholders filled, `NEEDS_REVIEW` markers cleared
- [x] Structural validation: all JSON parses, no dangling category/
      subcategory/unit references, `used_by` lists match both directions
- [ ] **Not yet done — belongs to Phase 9:** wiring this JSON into
      `backend/` (loading it, exposing it via an endpoint or bundling into
      frontend)
- [ ] **Not yet done — needs a human pass:** brand-name and colloquial-unit
      (debe, gorogoro, gunia) accuracy check against real Kenyan market
      reality; `school_uniforms` and `mitumba` niche templates for
      clothing_store declared but not built; `agrovet` type deferred
      entirely
- Living document even after "done" — Phase 10 feeds real usage data back into it

---

### Phase 9 — Sell-without-inventory + progressive catalog growth
**Goal:** selling never stops for a missing product; inventory grows
continuously against the Phase 8 taxonomy instead of a flat list. Depends
on Phase 8 (ready) plus wiring the taxonomy into the backend (not yet done).

- [ ] Wire `knowledge/` JSON into `backend/` — load it, expose via
      endpoint or bundle into frontend (carried over from Phase 8's
      leftover item)
- [ ] `TransactionItem.product` becomes nullable; add freeform `name` +
      `unit_price` fields for the unreconciled case
- [ ] Sale flow: cashier types a name + price if not in catalog; sale
      records immediately; item flagged unreconciled
- [ ] Reconciliation queue in Stock: owner assigns each unreconciled item
      to an existing product or creates a new one, picking from the
      taxonomy (category → subcategory → suggested common names/brands)
      instead of typing free text
- [ ] Onboarding: select business type → see taxonomy categories for that
      type → optionally add starter items now or skip entirely — inventory
      is never "completed" at onboarding, only started
- [ ] `has_inventory` flag (§2.1) lands here — distinguishes stocked items
      from services in both sale flow and reconciliation queue
- [ ] For service businesses: this is the *default* path, not a fallback —
      confirm UI doesn't frame it as "temporary until you finish cataloging"
- [ ] Within-business suggestions (§2.3, fast track): once a business has
      2+ items under the same category, surface other common brands/names
      as tap-to-accept suggestions on next add
- [ ] Instrumentation from day one: log keep/delete/edit on suggested
      items, log every custom item added, per business
- [ ] Reports handle unreconciled items gracefully (count toward revenue
      immediately, excluded from per-product breakdowns until reconciled)

---

### Phase 10 — Demo-driven taxonomy refinement
**Goal:** the 14-day demo period becomes a data source for improving the
Phase 8 taxonomy over time, not just a sales trial.

- [ ] Instrument (from Phase 9's ship date): which suggested categories/
      items get kept vs. deleted, which custom categories/items get
      created that aren't in the taxonomy yet, which brands recur across
      businesses, which units/spellings businesses actually use
      colloquially
- [ ] Periodic review cycle (cadence TBD — monthly? quarterly? — decide
      once there's enough demo volume) where taxonomy JSON gets updated
      based on what real demo businesses actually did
- [ ] Never "completes" — an ongoing maintenance loop, same as "inventory
      is never finished" applied to the taxonomy itself

---

### Phase 11 — Perishability tracking
**Goal:** expiry-date tracking for inorganic goods; spoilage-risk is a
stretch goal, not a v1 requirement.

- [ ] Expiry date field on Product (or per-stock-batch if lot-level
      tracking is wanted instead of product-level — decision needed)
- [ ] "Expiring soon" alert, same pattern as low-stock alerts
- [ ] Stretch, not v1: spoilage-risk estimate for organic goods (e.g. days
      since last stock-in as a rough proxy) — not true perishability
      modeling; revisit only if expiry-date tracking proves insufficient

---

### Phase 12 — Creditor UI / customer ledger
**Goal:** a real "who owes me what" view, not just a `CREDIT` tag on
individual sales with no identity attached.

- [ ] **Open question to confirm before building:** does this need a new
      `Customer` model (name/phone, not necessarily a full user account)
      to attach credit sales to an identity? Current schema has no
      customer identity — `CREDIT` is just a payment-method tag today.
- [ ] Customer ledger: running balance per customer, sale history against that balance
- [ ] Settle/partial-payment flow against an outstanding balance
- [ ] Creditor list view (who owes what, sorted by amount or age)

---

### Phase 13 — Cross-business sub-niche detection (adaptive onboarding, Stage 2)
**Goal:** the "learn from data" half of §2.2. Gated on real usage volume
within a type — scheduled to a data threshold, not a session.

- [ ] Co-occurrence analysis of custom-added items within a declared
      business type, once enough businesses of that type exist to make
      patterns meaningful (threshold TBD from real distribution)
- [ ] Sub-tag emergence (e.g. "plumbing & electrical hardware" as a
      detected sub-niche of HARDWARE)
- [ ] Soft-ask UX for new signups in a type with an established sub-tag —
      one follow-up question, never a silent guess
- [ ] Confirm terms of service / privacy policy language is live before
      this ships (§2.2 consent note)

---

### Phase 14 — More settings
**Goal:** placeholder — waiting on a concrete list. Known candidates
already discussed: global default low-stock threshold, receipt footer
text, default payment method, tax/VAT toggle. Not scoped further until the
list is provided.

---

### E-commerce / B2B marketplace — separate initiative, not a numbered phase
See §2.4. Own planning session, trust/dispute/fund-flow model decided
before any schema work, escrow/money-transmitter regulatory question still
open.

---

## 4. Sequencing

**Phase 6 (audit) → Phase 6.5 (notification abstraction layer — not
urgent/broken, but cheap to do early and before more code depends on
direct AT calls) → Phase 7 (graphs, can run in parallel with Phase 9's
wiring work) → Phase 9 (sell-without-inventory + progressive catalog —
Phase 8 taxonomy is done, this just needs to wire it in) → Phase 10
(demo-driven taxonomy refinement, ongoing from Phase 9's ship date) →
Phase 11 (perishability) → Phase 12 (creditor UI) → Phase 13
(cross-business sub-niche detection, data-gated) → Phase 14 (settings,
once list is provided) → [E-commerce, separate initiative, not sequenced
against the above]**

Phase 6.5 has no hard dependency on Phase 6 finishing first — they touch
different parts of the codebase — but doing the infra audit first means
Phase 6.5's new Redis-backed delivery logging (if that's the chosen
storage) lands on top of an already-confirmed-working Redis setup rather
than an assumed one.

**Open questions, still unanswered:**
1. Is there anything in daily use *today* that should jump this queue —
   something BizYangu is currently bleeding money or trust from that isn't
   reflected above?
2. Taxonomy v1 scope was resolved as "first-cohort subset" (9 types,
   built) rather than the full 100–150 — confirm whether to expand before
   or after pilot feedback comes in.
3. Brand-name and colloquial-unit accuracy in the built taxonomy — needs a
   human spot-check pass (§3.1) before Phase 9 exposes it to real onboarding.

---

## 5. Security plan (standing, not a phase)

Applies across all phases — not a one-time checklist, a baseline that
every new endpoint/feature must meet.

**Auth & authorization:** JWT access 15min / refresh 7 days with rotation
+ blacklist. OTP: 6-digit hashed, 10-min expiry, max 3 attempts, rate
limited (3/hour/phone). Role permissions enforced at the API view level
(OWNER full access, MANAGER all-but-billing/user-mgmt, CASHIER
sell+read-only-inventory+own-history). Every request tenant-isolated via
`IsSameBusiness` — business ID always from JWT, never from URL/query param.

**M-Pesa webhooks:** public endpoint validated via Safaricom IP allowlist,
signature verification where supported, idempotent on
`mpesa_receipt_number`, processed async via Celery, raw payloads stored
for audit.

**Input validation:** DRF serializers only, no raw SQL, file upload
MIME+extension+size checks (5MB cap), free-text fields sanitized, phone
numbers validated E.164 before OTP dispatch.

**API hardening:** HTTPS enforced, CORS whitelisted to the real frontend
origin only, `ALLOWED_HOSTS` never `*`, rate limiting via
`django-ratelimit` (OTP 3/hr/phone, login 10/hr/IP, sale recording
60/min/user, general API 300/min/user), `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `SECRET_KEY` from environment only.

**Data security:** `DEBUG = False` outside local dev, cost prices/business
financials excluded from cashier-role responses, no PII in logs, daily DB
backups even in prototype phase, `.env` never committed.

**Frontend:** JWT in `httpOnly` cookies (never `localStorage`), CSRF token
on all non-GET requests, API base URL from env not hardcoded, no sensitive
data in URL params, CSP header configured.

**Pre-pilot manual penetration checklist:** attempt cross-business data
access via ID manipulation; attempt cashier→owner role escalation via API;
attempt a negative-quantity sale; attempt >3 OTP submissions; attempt a
fake Daraja callback payload; attempt XSS via product name field.

---

## 6. Demo control system (standing, not a phase)

**Philosophy:** time-limited to prevent indefinite free use, but
degradation is graceful, never hostile. User keeps data and read access;
just can't write new transactions until they subscribe. Enforcement is
backend-only — frontend reflects state, never enforces it.

| Day | State | What happens |
|---|---|---|
| 1–10 | DEMO, silent | Full access, no mention of expiry |
| 11–13 | DEMO, warning | Soft banner: "Biashara yako ya majaribio inaisha siku {N}. Wasiliana na Lewis: 07XX XXX XXX" |
| 14 | EXPIRED | App read-only. Dashboard/reports still work. Writes blocked. |
| 14+ | EXPIRED, locked | Persistent full-screen overlay on dashboard with WhatsApp CTA |

**Backend:** `Business.is_demo_expired()` / `days_remaining()` model
methods; `IsNotExpired` DRF permission class blocking non-safe methods
when expired, applied alongside `IsSameBusiness` on every viewset; Celery
beat task `check_demo_expirations` runs daily at midnight; admin override
via Django admin or management command only — never via a public endpoint.

**Frontend:** demo state returned on `/api/v1/auth/me/`; `useDemoStore`
(Zustand) holds `subscription_status` + `days_remaining`; warning banner
at `days_remaining <= 3`, dismissible per session; non-dismissible overlay
on write screens when expired; write buttons show lock icon + toast before
the API call even fires.

**Security notes:** expiry enforced at API permission layer — disabling
frontend lock does nothing. `demo_expires_at` is server-set on creation,
never client-writeable. `subscription_status` never writeable via API.

---

## 7. Production deployment / pilot go-live checklist

Written fresh against the actual code in the handoff package — every item
checked against `backend/`, `frontend/`, and `docker-compose.yml` as they
exist, not assumed. Work top to bottom. Nothing in §7.8 (go-live smoke
test) happens before everything above it is checked.

### 7.0 Clean database
Starting production on a fresh DB, not migrating dev data over, is the
right call — dev data has fake businesses, sandbox M-Pesa transactions,
test accounts.

- [ ] Provision a **new** Postgres instance/DB — don't reuse the
      dev password (`M@$ter`) sitting in plaintext in `docker-compose.yml`
      and `backend/.env`. Generate a new random one.
- [ ] `python manage.py migrate` against the empty DB — already verified
      clean up to `0005_transaction_customer`, but run it for real against
      prod before anything else touches it.
- [ ] `python manage.py createsuperuser` — one admin account, don't carry
      over a dev superuser.
- [ ] **Do not** run any fixture/seed data for businesses, products, or
      transactions. After this step: empty schema + one admin user, nothing else.
- [ ] Confirm `knowledge/` (business types, categories, units, templates —
      read live from JSON, not seeded into the DB) is deployed as a
      sibling of `backend/` on the production host, matching the path
      `apps/knowledge/loader.py` expects (`Path(BASE_DIR).parent /
      'knowledge'`). This already broke once inside Docker until a bind
      mount was added — check explicitly on whatever platform is used, don't assume it carries over.

### 7.1 Secrets & environment — full rotation, not a copy
Every value below currently has a dev/sandbox value in `backend/.env`.

- [ ] `SECRET_KEY` — generate real: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- [ ] `DEBUG=False` — keep it. Never flip on in production even temporarily.
- [ ] `DB_PASSWORD` — new, generated, not `M@$ter`.
- [ ] `ALLOWED_HOSTS` — replace the cloudflare tunnel domain
      (`trends-powell-guam-wal.trycloudflare.com`) with the real
      production domain — tunnel domains change on every `cloudflared`
      restart, confirm a stable domain is used.
- [ ] `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` — same swap.
- [ ] `DEV_OTP_BYPASS` — remove entirely or set `False`. **Highest-severity
      item on this whole list**: if `True` leaks into production, anyone
      can log in to any phone number with `000000`. Double check after
      deploy — don't just trust the `.env` file.
- [ ] `AT_USERNAME` / `AT_API_KEY` — swap sandbox for live Africa's Talking credentials.
- [ ] `MPESA_ENV=production` (currently `sandbox`) — confirm this actually
      flips `apps/payments/daraja.py`'s base URL between
      `sandbox.safaricom.co.ke` and `api.safaricom.co.ke`.
- [ ] `MPESA_CONSUMER_KEY` / `MPESA_CONSUMER_SECRET` / `MPESA_SHORTCODE` /
      `MPESA_PASSKEY` — swap sandbox values (shortcode `174379` is
      Safaricom's public test till) for real Daraja production credentials.
- [ ] `MPESA_CALLBACK_URL` — real production domain, HTTPS, publicly
      reachable before registering with Safaricom.
- [ ] `MPESA_CALLBACK_IP_ALLOWLIST_DISABLED` — currently `True`. Decide
      deliberately whether to enable Safaricom's IP allowlist in
      production; leaving disabled is a reasonable pilot-stage tradeoff
      but should be a choice, not an oversight.
- [ ] `ADMIN_URL_PATH` — long random slug (e.g. `xk7-manage-2f9/`) — currently defaults to `admin/`.
- [ ] `SENTRY_DSN` — currently empty (sentry-sdk installed and wired in
      `settings/production.py` but reporting nowhere). Get a real DSN before go-live.
- [ ] `FCM_SERVICE_ACCOUNT_JSON` — decide now whether low-stock push
      notifications are in pilot scope. If not, leave empty (degrades
      gracefully). If yes, needs the full Firebase service account JSON as one line.

### 7.2 Backend deploy mechanics — the Dockerfile is dev-only
`backend/Dockerfile` currently runs `manage.py runserver` (single-threaded
dev server, no static file serving) and installs
`requirements/development.txt` (pulls in `django-debug-toolbar`). Neither
should run in production.

- [ ] Install `requirements/production.txt` (already has `gunicorn` and `sentry-sdk`) instead.
- [ ] App uses Django Channels for WebSockets (payment status, live
      reports — see `CHANNEL_LAYERS`/`ASGI_APPLICATION` in
      `settings/base.py`), so an ASGI-capable process is required, not
      plain gunicorn: `daphne -b 0.0.0.0 -p $PORT bizyangu.asgi:application`
      (what `docker-compose.yml`'s dev command already uses), or gunicorn
      with a uvicorn worker class. Pick one deliberately.
- [ ] Add `python manage.py collectstatic --noinput` to the deploy step —
      Whitenoise serves `STATIC_ROOT`, currently empty since nothing runs this.
- [ ] `python manage.py migrate --noinput` on deploy (already in compose
      command, keep it — safe *because* it's a clean DB with a verified
      migration chain per §7.0).
- [ ] **`docker-compose.yml` has no Celery worker or beat service at
      all**, despite `CELERY_BEAT_SCHEDULE` in `settings/base.py`
      scheduling the STK-timeout cleanup job every 5 minutes — it likely
      never runs unless started manually. Need `celery -A bizyangu worker`
      and `celery -A bizyangu beat` as long-running processes (or one
      combined `-B` process for a small pilot — fine at this scale, just
      know it's a single point of failure for both).
- [ ] No reverse proxy / TLS termination in `docker-compose.yml` —
      handled automatically on Render/Railway/Fly.io-style platforms; on a
      bare VM, nginx or Caddy is needed in front of daphne.

### 7.3 M-Pesa production cutover
- [ ] Confirm the Daraja **production** app is approved and live (not
      pending Safaricom review) before pointing `MPESA_ENV=production` at it.
- [ ] Run `apps/payments/management/commands/register_c2b.py` against
      production — exists in the repo already, but needs re-running
      against the production shortcode; sandbox registration doesn't carry over.
- [ ] One real end-to-end STK push with a small real amount (e.g. KES 1)
      as the first production payment test, before any pilot business touches it.
- [ ] Confirm the Celery beat STK-timeout sweep (§7.2) is actually running
      in production — the safety net for a stuck-payment bug already fixed once in dev.

### 7.4 OTP / SMS production cutover
- [ ] `DEV_OTP_BYPASS=False` (verify twice — listed in §7.1 too).
- [ ] Live Africa's Talking credentials in place.
- [ ] Register a proper alphanumeric Sender ID (e.g. `BizYangu`) before
      pilot — telco approval takes a few days, start early. Without it,
      `apps/accounts/services.py`'s `send_otp_sms()` sends from AT's
      shared default sender, which reads as generic/spammy to a
      first-time user.
- [ ] Send a real OTP end-to-end after cutover — actually receive an SMS, don't just trust config.

### 7.5 Frontend / APK
- [ ] `NEXT_PUBLIC_API_URL` — baked in at `next build` time, must point at
      the real production API domain, not the cloudflare tunnel.
- [ ] Rebuild the APK after that change — it won't pick up a new API URL
      at runtime, only at build time.
- [ ] Decide and document the APK signing approach before the first real
      install — no keystore currently exists in the project. Debug/
      self-signed key is fine for a 3–5 business pilot, but write down
      which one — losing an undocumented keystore means no updates to the
      same app without users uninstalling first.
- [ ] One real device smoke test of the rebuilt APK against the
      production backend before handing it to a pilot business — login →
      sell → STK push → dashboard, at minimum.

### 7.6 Monitoring & backups
- [ ] **Do one real Postgres restore-from-backup test before any pilot
      data exists.** Not "backups are configured" — actually take a
      backup, actually restore it somewhere, actually confirm the data is there.
- [ ] Confirm Sentry is actually receiving events post-deploy — trigger
      one deliberate test error and check it shows up.
- [ ] Basic usage instrumentation — at minimum transaction count and
      last-active timestamp per business, queryable from Django admin, so
      "did they actually use it yesterday" is answerable without asking.
      (Already scoped in Phase 6 above — still open.)

### 7.7 Access & operational readiness
- [ ] Admin URL moved off `/admin/` (§7.1) and only the founder has the credentials.
- [ ] One-page install guide for a non-technical Android user: "allow
      unknown sources → install APK → open." Pilot users are duka owners, not developers.
- [ ] Feedback channel (WhatsApp group with founder + pilot owners) set up
      and tested before the first business goes live, not after the first complaint.
- [ ] Feature scope frozen at whatever ships in this deploy — no new
      features mid-pilot unless something is actively broken.

### 7.8 Go-live smoke test — do in order, on production, before real users
1. [ ] Fresh DB migrated clean, superuser created (§7.0)
2. [ ] Load the app, confirm `DEBUG=False` (a deliberately broken URL
       shows a generic error page, not a stack trace)
3. [ ] Sign up / OTP login with a real phone number, real SMS received
4. [ ] Complete business setup / onboarding
5. [ ] Add a product, make a sale, confirm stock decrements
6. [ ] Real M-Pesa STK push for a small real amount, confirm it reaches
       `CONFIRMED` (not stuck `PENDING`)
7. [ ] Confirm reconciliation queue, dashboard, and reports all load with
       real data from steps 5–6
8. [ ] Trigger a deliberate backend error, confirm it shows up in Sentry
9. [ ] Kill and restore the DB from a backup taken after step 7, confirm data survives

Only after all nine pass: hand the APK to the first real pilot business.

### 7.9 Rollback plan
- [ ] Know, in writing, how to roll back before it's needed: keep the
      previous known-good backend deploy available (previous Docker image
      tag or git commit), and take a DB backup immediately before every
      future deploy once pilot data exists — not just on a schedule.

---

## 8. Non-functional requirements

| Requirement | Target | Notes |
|---|---|---|
| Time to first sale | < 10 minutes | Fresh install to first recorded transaction |
| POS transaction record time | < 30 seconds | Tap item → confirm sale → receipt |
| Dashboard load time | < 2 seconds | On 3G connection |
| Offline capability | Core POS only | Sales queue offline, sync on reconnect |
| Concurrent users | 1–3 per business | Prototype target, scale later |
| Uptime (prototype) | Best effort | Not SLA-bound |
| Data retention | All data kept | No deletion of transaction records ever |
| Audit trail | Complete | Every stock movement traceable to a user and timestamp |

---

## 9. Key design decisions & rationale (log — don't re-litigate without new info)

| Decision | Rationale |
|---|---|
| Progressive catalog onboarding, not full stock count | Field research: an established shop owner declined the prototype specifically because full stock entry felt too painful |
| Stock level derived from transaction history | Accuracy builds over time; no artificial "opening stock" pressure |
| WhatsApp for receipts/notifications | 100% of target users already have WhatsApp; no app download needed to receive a receipt |
| Kiswahili-first copy | Field interviews conducted in Kiswahili; most respondents more comfortable in it |
| Dark-first UI | LN Design System mandate; also less glaring behind a counter in mixed shop lighting |
| Django backend + Next.js frontend + Capacitor wrapper | Separation of concerns — data/logic layer, presentation layer, mobile wrapper, three clearly bounded responsibilities |
| No subscription billing in prototype | Field data showed zero deposit conversions; product needs to prove itself before billing adds friction |
| Time-limited demo, graceful degradation | Prevents indefinite free use without being hostile; read-only expiry keeps user's data accessible; enforced at API level |
| Boutique → Clothing Store rename, niche field | School-uniform and mitumba sellers are structurally different enough (suppliers, customer relationship, seasonality) to need their own niche templates |
| Wholesale doesn't reuse retail categories | Bulk packaging/units (`sack_50kg`, `tonne`, `crate`) are a structural difference, not just a quantity difference |
| Auto spares vs. garage kept as two templates | Sometimes the same yard, sometimes not — a tagging/onboarding concern, not a taxonomy merge |
| Vehicle make/model fitment excluded from auto_spares taxonomy | Capturing every make/model combination would violate the curated-not-complete principle; fitment is a per-business product detail |
| Chang'aa/local spirits excluded from bar taxonomy | Licensing sensitivity unresolved — revisit only once there's a real answer |
| Animal feed deferred to a future `agrovet` type | Not one of the 9 first-cohort types; adding it is future Phase 8 scope |
| M-Pesa float excluded from stock tracking | Cash-equivalent, not a stocked physical item — taxonomy-level flag only, float-balance handling itself is unbuilt |
| Build the OTP/notification routing layer in-house rather than adopt Robase | Robase's multi-provider failover is exactly the abstraction BizYangu needs, but using it means trusting a third party's routing for a login-blocking path with no visibility into which carrier was actually used; owning it means owning the failover logic and the delivery data |
| Keep Africa's Talking wired in as one of multiple SMS providers, not remove it | AT was never actually broken — its real pricing (KES 0.8/SMS pilot tier, KES 8,700 Safaricom-only Sender ID) is normal for Kenya, not the KES 14K blocker it first looked like; the KES 14,100 figure was the bundled Safaricom+Airtel price, not what BizYangu needs |
| MobiWave added as a second SMS provider ahead of eSMS Africa | Verified pricing (KES 0.35/SMS at pilot volume) is cheapest of the three at BizYangu's actual scale; eSMS Africa's real tiered pricing is more expensive than AT until spend exceeds ~KES 129,500/month despite advertising the lowest headline rate |

---

## 10. Post-prototype roadmap (explicitly out of scope for now)
- Subscription billing via M-Pesa
- Multi-branch support
- Advanced loss analytics
- Play Store / App Store submission
- VPS deployment (move off tunnels/pilot hosting)
- Marketing website
- CompanyOS AI team activation
- Payroll module
- KRA iTax integration
- E-commerce / B2B marketplace (§2.4 — separate initiative)

---

## 11. Session continuity protocol

Each build session should begin by uploading the current state of the
codebase. Minimum files to bring:

| File | Why |
|---|---|
| `backend/apps/*/models.py` | Data model state |
| `backend/apps/*/serializers.py` | API contract |
| `backend/apps/*/views.py` | Endpoint logic |
| `backend/bizyangu/settings/base.py` | Config state |
| `backend/requirements/base.txt` | Dependency state |
| `frontend/app/**/*.tsx` (changed files) | UI state |
| `frontend/lib/api.ts` | API client state |
| `capacitor.config.ts` | Mobile config |
| `knowledge/**/*.json` | Taxonomy state (once Phase 9 wires it in) |

Deliverables from each session: patch of changed files only, with a
`CHANGES.md` listing what was added, modified, or fixed.

---

*BizYangu Master Plan — consolidated August 2026, updated same month with
Phase 6.5 (notification abstraction layer). This document is the living
plan going forward — update it in place rather than creating a v4.*
