# BizYangu — Build Plan v3
**Supersedes:** `BizYangu_Build_Plan_v2.md` (kept in repo for history)
**Written:** July 2026, after feedback on v2's Phase 8/9/12 split — restructured
around a single through-line: *let selling happen immediately while the
inventory database builds itself in the background, against a curated
taxonomy rather than a flat product list.*

Phases 0–5.6 are unchanged from v2 (all complete — see that document for
detail, not repeated here). Everything below Phase 6 is restructured.

---

## 1. Where things stand (unchanged from v2)

| Phase | What | Status |
|---|---|---|
| 0–5.6 | Skeleton through Security hardening | ✅ Complete — see `BizYangu_Build_Plan_v2.md` §1 for detail |

Still open, unchanged: automatic 9pm EOD trigger, M-Pesa PDF statement
import, barcode scanning, partial-refund UI. None block anything below.

---

## 2. The reframe

v2 treated "sell without inventory" and "progressive onboarding" as two
adjacent phases. They're actually one system with two moving parts:

> **Selling must never stop for a missing product. Inventory is never
> "finished" — it grows continuously as the business uses the app, against
> a curated taxonomy that makes every addition fast and consistent instead
> of a blank text field.**

The taxonomy is the piece that was missing from v2. Without it, "curated
preset lists per business type" (v2 Phase 9) is just a smaller version of
the "list every product sold in Kenya" trap — a flat list still can't
power suggestions, can't tell a service from a good, and can't distinguish
"Cement" the category from "Bamburi Cement" the brand-item a specific
business actually stocks.

### 2.1 The hierarchy

```
Business Type
    ↓
Category
    ↓
Subcategory
    ↓
Common Item Names
    ↓
Common Brands
    ↓
Units
```

Example:
```
Hardware → Paint → Interior/Emulsion Paint → "Emulsion Paint" → Crown, Basco, Duracoat → 4L/20L, Bucket
```

Service-type businesses (2.2 below, and §2.1 of v2) live in the same
structure — a Category can simply have no brand/unit slot:
```
Salon → Hair Services → Cut / Color / Treatment → (no brand, no unit — priced per service)
```

**What the knowledge base stores:** business types, categories,
subcategories, common item names, common brands, units — structure and
vocabulary. **What it does NOT store:** actual products. Products belong to
each business, created by that business, seeded from and suggested against
the taxonomy but never pre-populated wholesale as if the taxonomy were a
product catalog.

```
knowledge/
    business_types.json
    categories.json
    subcategories.json
    brands.json
    units.json
    templates/
        hardware.json
        kiosk.json
        boutique.json
        agrovet.json
        salon.json          ← service-type template, no brand/unit fields
        ...
```

### 2.2 Service businesses (carried over from v2 §2.1, now folded in)
Unchanged principle, now expressed structurally: a service-type template in
the knowledge base has categories/subcategories but no brand or unit
fields, and the `has_inventory` flag on Product (or equivalent) still
governs which stock-related UI/reports apply. This is no longer a
carve-out bolted onto the goods-first model — it's just another shape the
same taxonomy supports.

### 2.3 Two different kinds of "smart," on two different timelines
Worth being explicit that these are not the same feature, because they
have very different costs and gates:

- **Within-business suggestion (fast, no gate).** A business adds "Bamburi
  Cement," then "Simba Cement" — the system now has enough signal from
  *that business alone* to suggest "Mombasa Cement," "National Cement,"
  "Savannah Cement" from the Cement category's known-brands list next time
  they add a product in that category. This needs nothing but the
  taxonomy's brand list plus that business's own item history. Can ship
  as soon as the taxonomy + progressive catalog exist.
- **Cross-business sub-niche detection (slow, data-gated).** Detecting that
  a cohort of HARDWARE businesses are actually plumbing-and-electrical
  specialists, and adjusting what *new* signups in that type see — this is
  v2's old Phase 12, unchanged in substance, still gated on real usage
  volume within a type before it's trustworthy. Kept as its own later phase
  (§3, Phase 13 below) precisely because conflating it with the fast,
  cheap, per-business suggestion above would make the easy win wait on the
  hard one.

### 2.4 Who builds the taxonomy content — open question, not yet answered
100–150 business types × 10–30 categories each × subcategories × brands ×
units is a real content-curation project, not a schema decision — hundreds
of hours if done with real care, since a wrong brand name or malformed
category baked into a "proprietary knowledge base" is worse than an
obviously-incomplete one. Two open decisions before Phase 8 (Knowledge Base
Curation) can start:
- **Scope of v1**: the full 100–150 types, or a much smaller set matching
  your actual first cohort's business types, expanding as real demand
  appears?
- **Who curates**: your own research, someone else's time, or an
  LLM-assisted first draft that a human then verifies line-by-line against
  actual Kenyan market reality before it ships? (If LLM-assisted, that
  verification step is not optional — a hallucinated brand or category
  structure is exactly the failure mode this whole approach is trying to
  avoid.)

Both need an answer before Phase 8 gets scheduled, not during it.

---

## 3. Phases 6 onward (restructured)

### Phase 6 — Sessions, JWT, Redis, N+1 audit
*(unchanged from v2 — see that document for the full checklist)*
No product decisions required. Confirms the infrastructure underneath
everything else is solid before more gets built on top of it.

---

### Phase 7 — Reports: growth & profit graphs
*(unchanged from v2 — see that document for the full checklist)*
Cheapest phase on the list, mostly frontend. No dependency on the taxonomy
work below — can run in parallel with Phase 8 if useful.

---

### Phase 8 — Knowledge Base Curation *(new — inserted before onboarding, per feedback)*
**Goal:** build the taxonomy described in §2.1 before any onboarding or
inventory-growth feature depends on it. This phase produces version-controlled
JSON, not app code.

- [ ] **Decision first** (§2.4): confirm v1 scope (full type list vs. first-
      cohort subset) and curation approach (manual vs. LLM-assisted-then-
      verified) before starting
- [ ] Business types list (Kenyan SME-relevant — duka, hardware, boutique,
      stationery, agrovet, salon/barbershop, and other common service
      types), scoped per the decision above
- [ ] Per business type: 10–30 core categories
- [ ] Per category: subcategories where useful (not forced where they'd add
      noise — e.g. a simple kiosk may not need subcategories a hardware
      store does)
- [ ] Common brands and units of measure, attached at the category/
      subcategory level
- [ ] Service-type templates explicitly included (§2.2) — not an
      afterthought pass once goods-type templates are done
- [ ] Store as version-controlled JSON (`knowledge/` structure in §2.1) —
      explicitly no `products.json`; products are created by businesses,
      never pre-populated wholesale
- [ ] This is a living document even after "done" — Phase 10 below feeds
      real usage data back into it

---

### Phase 9 — Sell-without-inventory + progressive catalog growth
**Goal:** the two v2 phases (8: sell-without-inventory, 9: onboarding
presets) merged into one continuous flow, now built against the Phase 8
taxonomy instead of a flat preset list. Depends on Phase 8 existing, at
least in an initial-scope form.

- [ ] **Selling never stops for a missing product.** Sale flow: cashier
      types a name + price if it's not in the catalog; sale records
      immediately; item is flagged unreconciled. `TransactionItem.product`
      becomes nullable, freeform `name` + `unit_price` fields added for
      the unreconciled case — matches v2 Phase 8's schema note, unchanged
- [ ] Reconciliation queue in Stock: owner assigns each unreconciled item to
      an existing product or creates a new one, picking from the Phase 8
      taxonomy (category → subcategory → suggested common names/brands)
      rather than typing free text every time
- [ ] Onboarding: select business type → see the Phase 8 taxonomy's
      categories for that type → optionally add a few starter items now, or
      skip entirely and let the catalog build itself purely through selling
      — **inventory is never "completed" at onboarding, only started**
- [ ] `has_inventory` flag lands here (carried from v2 §2.1) — needed to
      distinguish stocked items from services in both the sale flow and the
      reconciliation queue
- [ ] Within-business suggestions (§2.3, fast track): once a business has
      added 2+ items under the same taxonomy category, surface the
      category's other common brands/names as suggestions on next add —
      never auto-added, always a tap-to-accept suggestion
- [ ] Reports handle unreconciled items gracefully (count toward revenue
      immediately, excluded from per-product breakdowns until reconciled) —
      unchanged from v2

---

### Phase 10 — Demo-driven taxonomy refinement
**Goal:** the 14-day demo period becomes a data source for improving Phase
8's taxonomy over time, not just a sales trial. New phase, direct result of
the feedback document's Principle 8.

- [ ] Instrument (from the moment Phase 9 ships): which preset categories/
      items get kept vs. deleted, which custom categories/items get created
      that aren't in the taxonomy yet, which brands recur across
      businesses, which units and spellings businesses actually use
      colloquially (Kenyan market naming conventions may differ from
      "textbook" naming)
      instrumentation, this phase is the review/update cycle
- [ ] Periodic review cycle (cadence TBD — monthly? quarterly? — decide
      once there's enough demo volume to make a cycle meaningful) where
      taxonomy JSON gets updated based on what real demo businesses
      actually did
- [ ] This phase never "completes" — it's an ongoing maintenance loop, not
      a one-time build, same as the "inventory is never finished" principle
      applied to the taxonomy itself

---

### Phase 11 — Perishability tracking
*(unchanged from v2 Phase 10 — see that document for the full checklist)*
Expiry-date tracking for inorganic goods is v1; organic spoilage-risk
estimation is an explicit stretch goal, not required for this phase to ship.

---

### Phase 12 — Creditor UI / customer ledger
*(unchanged from v2 Phase 11 — see that document for the full checklist,
including the open question on whether a new `Customer` model is needed)*

---

### Phase 13 — Cross-business sub-niche detection
*(unchanged in substance from v2 Phase 12, renumbered; see §2.3 above for
why this is kept separate from and later than the within-business
suggestions in Phase 9)*
Gated on real usage volume within a business type — not scheduled to a
session, scheduled to a data threshold reached via Phase 10's ongoing
instrumentation.

---

### Phase 14 — More settings
*(unchanged from v2 Phase 13 — placeholder, waiting on your concrete list)*

---

### E-commerce / B2B marketplace — separate initiative, not a numbered phase
*(unchanged from v2 §2.3 — own planning session, trust/dispute/fund-flow
model decided before any schema work, escrow/money-transmitter regulatory
question still open and unresolved, framed as its own product identity for
Duka-owner-to-customer commerce, B2B-first)*

---

## 4. Sequencing

**Phase 6 (audit) → Phase 7 (graphs, can run in parallel with 8) → Phase 8
(Knowledge Base Curation — decisions in §2.4 needed first) → Phase 9
(sell-without-inventory + progressive catalog, depends on 8) → Phase 10
(demo-driven taxonomy refinement, ongoing from Phase 9's ship date) → Phase
11 (perishability) → Phase 12 (creditor UI) → Phase 13 (cross-business
sub-niche detection, data-gated) → Phase 14 (settings, once list is
provided) → [E-commerce, separate initiative, not sequenced against the
above]**

Standing open question, still unanswered from prior sessions: is there
anything in daily use *today* that should jump this queue?

New open questions from this restructuring, both need answers before Phase
8 starts:
1. Taxonomy v1 scope — full 100–150 business types, or first-cohort subset?
2. Taxonomy curation approach — manual research, delegated, or
   LLM-assisted-then-human-verified?

---

*`BizYangu_Build_Plan_v2.md` and `BizYangu_Build_Plan_v1.md` both stay in
the repo unmodified as history. This document is the living plan going
forward.*
