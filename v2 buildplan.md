# BizYangu — Build Plan v2
**Supersedes:** `BizYangu_Build_Plan_v1.md` (kept in the repo for history — don't delete it)
**Written:** July 2026, after the Phase 5 + Settings/Staff-Invite sessions and a dedicated roadmap discussion.

This is a restructuring, not a rewrite from scratch. Phases 0–5 below are the
original plan, marked complete. Everything from Phase 6 onward is new —
derived from a discussion session, not yet built. Where a decision is still
open, it's flagged explicitly rather than guessed at.

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
| 5.5 | Settings + Staff Invite | ✅ Complete — business profile edit, staff list/invite/remove, `/join` acceptance flow, all validated against a real DB |
| 5.6 | Security/hygiene pass | ✅ Complete — general API rate limiting, Sentry actually initialized, admin URL moved off default path |

Still open from earlier phases, unchanged by this restructuring:
- Automatic 9pm EOD WhatsApp trigger (needs a Celery beat task + a decision on unattended send mechanism)
- M-Pesa PDF statement import
- Barcode scanning
- Partial-refund UI (backend supports it, no button calls it yet)

None of these block anything below — they're just still on the list.

---

## 2. Cross-cutting principles for everything from here on

These aren't phases — they're constraints that apply *across* several of the
phases below, and getting them wrong early costs more later than building
them in from the start.

### 2.1 Service businesses are a first-class case, not an edge case
Salons, barbershops, consultancies, repair shops — no physical stock. This
touches:
- **Catalog model**: needs a `has_inventory: bool` (or equivalent) on
  Product, defaulting appropriately, so stock-tracking fields
  (`current_stock`, `low_stock_threshold`, `unit`) are genuinely optional —
  not just zero-defaulted in a way that triggers false "out of stock" alerts.
- **Onboarding presets**: service-type entries (common services + typical
  pricing) alongside physical-goods presets from day one, not bolted on
  after the fact.
- **Reports**: "top products by units sold" → needs a service-shaped
  equivalent ("top services by revenue/bookings"). Loss and perishability
  reports should cleanly not apply, not show zeros.
- **Sell-without-inventory (Phase 8 below)**: for a service business this
  isn't a temporary bridge until stock is counted — it's the permanent,
  first-class path. Nothing here should assume "eventually gets reconciled
  into a stock count."

This needs to be decided as part of the catalog/onboarding schema work in
Phase 9, not retrofitted after.

### 2.2 Adaptive onboarding is two stages, not one
Agreed shape from the discussion:

- **Stage 1 (Phase 9, build now):** static, curated preset lists per
  business type — including service types (2.1). Non-negotiable regardless
  of anything adaptive — there's no data to adapt from without this
  existing first. Instrument it from day one: log which preset items a
  business keeps vs. deletes vs. edits, and log every custom (non-preset)
  item a business adds. This logging has zero behavioral effect at this
  stage — it's pure data collection, so the adaptive stage has something
  real to work from later.

- **Stage 2 (Phase 12, later):** sub-niche detection *within* a declared
  type — e.g. a HARDWARE business whose custom-added items cluster around
  plumbing/electrical items becomes a candidate for a "plumbing & electrical
  hardware" sub-tag, detected via co-occurrence of custom items across
  businesses of the same declared type, not a trained model. New signups in
  a type with an established sub-tag get asked one soft follow-up question
  ("Does your hardware mostly deal in plumbing & electrical, or general
  hardware?") rather than the system silently guessing — a wrong silent
  guess is worse UX than one extra tap.

  **Gate for Phase 12:** don't build this until there's a real distribution
  of custom items across a meaningful cohort within a type (the actual
  minimum count is a decision to make once we can see the real data — not
  a number to guess now).

- **Consent**: covered in your terms of service / privacy policy — using
  aggregated cross-business product data to improve suggestions for other
  businesses is disclosed there. Noted here so it's not forgotten when
  Phase 12 actually gets built.

### 2.3 E-commerce/B2B marketplace is a separate initiative, not a phase
Deliberately excluded from the numbered phases below. When it's time:
- It gets its own planning session, starting with the trust/dispute/
  fund-flow model before any schema work — that's the part that determines
  whether shop owners trust it, not the UI.
- **Regulatory flag, not yet resolved:** the discussion landed on BizYangu
  *orchestrating* the transaction (order state, delivery confirmation,
  dispute flagging) while money moves directly M-Pesa-to-M-Pesa between the
  two businesses, released on a trigger — rather than BizYangu's own account
  ever holding funds. The moment the platform itself holds someone else's
  money pending a condition, it's in money-transmitter/PSP territory under
  the National Payment System Act, which is a licensing and compliance
  workstream independent of engineering effort, and not something to walk
  into by default. This needs actual input from someone who knows Kenyan
  fintech regulation before it's decided either way — not an assumption
  baked into a schema.
- Framed as its own product identity for Duka-owner-to-customer commerce
  (your words: "a new BizYangu customer group"), B2B-first over B2C, given
  the supply-networking angle is the more defensible initial use case.
- No further scoping here until that dedicated session happens.

---

## 3. Phases 6 onward

### Phase 6 — Sessions, JWT, Redis, N+1 audit
**Goal:** confirm the infrastructure underneath everything else is actually
solid, before building more on top of it. No product decisions required —
this is a "does what we already built work correctly" pass, not new
features.

- [ ] Trace every list/detail endpoint for missing `select_related` /
      `prefetch_related` — reports, transactions, catalog, staff list are
      the highest-traffic candidates
- [ ] Confirm refresh-token rotation is actually hitting the blacklist (not
      just configured in `SIMPLE_JWT` — verify the blacklist app is
      installed and the rotation is observably working)
- [ ] Confirm what's actually running Redis today vs. SQLite/in-memory
      fallback in dev — Channels layer, cache backend, and Celery broker
      may currently be three different things by accident rather than
      design
- [ ] Session/cookie lifetime sanity check against the JWT lifetimes
      already set (15min access / 7day refresh) — confirm the frontend's
      refresh flow actually exercises this correctly under real network
      conditions (flaky connections, backgrounded app)
- [ ] Document findings — this phase produces a written audit + fixes, not
      new UI

---

### Phase 7 — Reports: growth & profit graphs
**Goal:** turn the existing daily/period aggregation into visual trend data.
Cheapest phase on the list — mostly frontend, `recharts` is already a
dependency.

- [ ] Revenue-over-time line chart (reuses `/reports/period/`'s
      `daily_breakdown`, already computed)
- [ ] Profit/margin trend (needs product performance data extended across
      a date range rather than single-period — check whether this is a new
      endpoint or a reshape of `/reports/products/`)
- [ ] Period-over-period growth indicator (this month vs. last month, this
      week vs. last week)
- [ ] Visual treatment for service-vs-goods businesses (2.1) — a service
      business's growth chart shouldn't reference stock/margin concepts
      that don't apply to it

---

### Phase 8 — Sell without inventory + reconciliation queue
**Goal:** let a cashier sell an item that isn't in the catalog yet, without
breaking the sale flow, then let the owner reconcile it afterward.

- [ ] `TransactionItem.product` becomes nullable; add freeform `name` +
      `unit_price` fields for the unreconciled case
- [ ] Sale flow: cashier can type a name + price instead of picking from
      catalog, same UI otherwise
- [ ] "Unreconciled items" queue in Stock — owner assigns each to an
      existing product or creates a new one after the fact
- [ ] For service businesses (2.1): this is the *default* path, not a
      fallback — confirm the UI doesn't frame it as "temporary until you
      finish cataloging"
- [ ] Reports need to handle unreconciled items gracefully until assigned
      (they still count toward revenue, just not toward per-product
      breakdowns until reconciled)

-   Never block a sale.
-   Allow unreconciled items.
-   Maintain an Items Awaiting Reconciliation queue.
-   Let owners create or link products later.
-   Service businesses use this as the default workflow.
---

### Phase 9 — Progressive onboarding: static presets (adaptive Stage 1)
**Goal:** business-type-aware onboarding — pick a type, get a relevant
starter catalog instead of a blank list. See §2.2 for the two-stage
adaptive plan; this phase is Stage 1 only.

- [ ] Curated preset dataset per business type common in Kenya — duka,
      hardware, boutique, stationery, salon/barbershop, and other service
      types (2.1) — starter products *and* starter services with typical
      pricing where applicable
- [ ] Onboarding flow: select type → review/edit preset list → adjust
      before first save (not a forced accept-all)
- [ ] Instrumentation from day one: log keep/delete/edit on preset items,
      log every custom item added, per business — zero behavioral effect
      now, this is the data Stage 2 (Phase 12) will need
- [ ] `has_inventory` flag (2.1) lands here, since preset data needs it to
      distinguish stocked items from services

-   Curated JSON knowledge base.
-   Templates contain categories, services, units, supplier types and
    settings.
-   Onboarding: Business Type → Suggested Categories → Review → Start
    Selling.
-   Inventory grows through daily operation.
-   Instrument presets kept/removed, custom categories, brands, products
    and units.

**Design Principle:** BizYangu curates knowledge, not inventories.


### Phase 10 — Perishability tracking
**Goal:** expiry-date tracking for inorganic goods; spoilage-risk as a
stretch goal, not a v1 requirement.

- [ ] Expiry date field on Product (or per-stock-batch, if you want
      lot-level tracking rather than product-level — decision needed here)
- [ ] "Expiring soon" alert, same pattern as low-stock alerts
- [ ] Stretch, not v1: spoilage-risk estimate for organic goods (e.g. days
      since last stock-in as a rough proxy) — explicitly not true
      perishability modeling; revisit only if expiry-date tracking proves
      insufcient for organic-goods businesses

---

### Phase 11 — Creditor UI / customer ledger
**Goal:** a real "who owes me what" view, not just a `CREDIT` tag on
individual sales with no identity attached.

- [ ] **Open question to confirm before building:** does this need a new
      `Customer` model (name/phone, not necessarily a full user account) to
      attach credit sales to an identity? Current schema has no customer
      identity at all — `CREDIT` is just a payment-method tag on a
      transaction today.
- [ ] Customer ledger: running balance per customer, sale history against
      that balance
- [ ] Settle/partial-payment flow against an outstanding balance
- [ ] Creditor list view (who owes what, sorted by amount or age)

---

### Phase 12 — Adaptive onboarding: sub-niche detection (Stage 2)
**Goal:** the "learn from data" half of §2.2. Gated on Phase 9 having run
long enough to produce real data — not scheduled to a specific session,
scheduled to a data threshold.

- [ ] Co-occurrence analysis of custom-added items within a declared
      business type, once enough businesses of that type exist to make
      patterns meaningful (threshold TBD from real distribution, not
      guessed in advance)
- [ ] Sub-tag emergence (e.g. "plumbing & electrical hardware" as a
      detected sub-niche of HARDWARE)
- [ ] Soft-ask UX for new signups in a type with an established sub-tag —
      one follow-up question, never a silent guess
- [ ] Confirm terms of service / privacy policy language (your
      responsibility, already agreed) is live before this ships, since it's
      the point where cross-business aggregate data starts actually
      changing what an individual business sees

---
# UPDATED SECTION --- §2.2 Progressive onboarding is continuous, adaptive onboarding is smarter

Onboarding is continuous rather than a one-time setup. Businesses should
start operating within minutes, with inventory growing organically.
Sales always take priority over inventory completeness.

Knowledge base JSON should contain Business Types, Categories,
Subcategories, Brands, Units, Supplier Types and Expense
Categories---not a complete national product list.

### Phase 13 — More settings
**Goal:** placeholder phase — waiting on your concrete list. Known
candidates already discussed: global default low-stock threshold, receipt
footer text, default payment method, tax/VAT toggle. Not scoped further
until you send the list.

---

## 4. Sequencing

Suggested order, unchanged from the discussion and not yet contested:

**Phase 6 (audit) → Phase 7 (graphs) → Phase 8 (sell without inventory) →
Phase 9 (onboarding presets) → Phase 10 (perishability) → Phase 11
(creditor UI) → Phase 12 (adaptive onboarding) → Phase 13 (settings, once
list is provided) → [E-commerce, separate initiative, own planning session,
not sequenced against the above]**

Open standing question from last session, still unanswered: is there
anything in daily use *today* that should jump this queue — something
BizYangu is currently bleeding money or trust from that isn't reflected
above?

---

*This document is the living plan going forward. `BizYangu_Build_Plan_v1.md`
stays in the repo unmodified as a record of the original phases — reference
it for historical context on Phases 0–5, not for anything past that point.*
