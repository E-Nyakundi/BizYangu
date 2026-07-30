# BizYangu Knowledge Base — Lexicon v1
**Per Build Plan v3, Phase 8 (Knowledge Base Curation).**

Taxonomy — categories, subcategories, common item names, brands, units —
for the first 9 business types agreed in the July 2026 discussion.
**All 107 brand placeholders have been reviewed and filled in** (July 2026,
second pass) — no `NEEDS_REVIEW` markers remain anywhere in `templates/`.

## Validation pass (July 2026, third review)

- Removed `templates/boutique.json` — a stale pre-decision draft left over
  from before the `boutique` → `clothing_store` rename (see "Decisions
  made" below). It still had `NEEDS_REVIEW`/empty-brand placeholders and
  wasn't referenced anywhere in `backend/` or `frontend/`, so it was dead
  weight rather than a real second template.
- Ran a full cross-reference check across all 9 remaining templates: every
  `category_id`, `subcategory_id`, and `unit` they reference resolves to a
  real entry in `categories.json` / `subcategories.json` / `units.json`
  (no dangling references), and every category's `used_by` list in
  `categories.json` now matches, in both directions, what its templates
  actually reference — including the `retail_addon` block in
  `salon_barbershop.json`, which uses a different shape than the main
  `categories` list and wasn't covered by the earlier structural pass.
  0 errors found.
- **Not yet done, flagged for Phase 9:** none of this JSON is loaded by
  `backend/` yet. Phase 8 was scoped as "produces version-controlled JSON,
  not app code" per the build plan, so this is expected — but it means
  wiring `knowledge/` into onboarding/reconciliation (reading these files,
  exposing them via an endpoint or bundling them into the frontend) is
  still open work for Phase 9, not something already half-built.

## What's in here

```
knowledge/
    business_types.json   ← the 9 types, their "kind" (goods/service), notes
    categories.json        ← every category, once, with which types use it
    subcategories.json     ← subcategories, only where they add real value
    units.json              ← shared unit vocabulary + colloquial variants
    templates/
        hardware.json
        bar.json
        kiosk.json
        clothing_store.json     ← niche="boutique"; school_uniforms/mitumba niches declared, not yet built
        wholesale.json
        salon_barbershop.json   ← service type: no brand/unit on services
        cereals_grains.json
        auto_spares.json
        garage.json              ← service type: no brand/unit on services
```

## Design decisions made while building this (flagging so you can push back)

- **Shared categories are defined once** in `categories.json` and referenced
  by id from multiple templates (e.g. `soft_drinks_water` is used by both
  `bar` and `kiosk`) — avoids the same category drifting out of sync if
  defined twice.
- **Wholesale deliberately does NOT reuse the retail shared categories** —
  it has its own `wholesale_foodstuffs`/`wholesale_household`/etc. category
  ids, because bulk packaging and units (`sack_50kg`, `tonne`, `crate`) are
  a real structural difference from single-piece retail, not just a
  quantity difference.
- **Service-type templates (`salon_barbershop`, `garage`) have no brand or
  unit fields on their services** — a haircut isn't a brand+unit item, it's
  priced per `service`/`session`. `salon_barbershop.json` also has a
  `retail_addon` section for the physical products salons commonly also
  sell (hair oil, shampoo) — that slice IS goods-shaped, brands and units
  included.
- **Auto spares vs. garage kept as two separate templates**, per your
  answer that these are sometimes the same yard and sometimes not — see
  `combinable_with` in `business_types.json`. This is a tagging/onboarding
  concern, not a taxonomy merge.
- **Vehicle make/model fitment is NOT in the auto_spares taxonomy** —
  "brake pads" is one item, not "brake pads — Toyota Probox" /
  "brake pads — Honda Fit" / etc. Capturing every make/model combination
  would violate the curated-not-complete principle from your original
  feedback. Fitment is left as a per-business product detail.
- **Growth-path relationships** (kiosk → retailer → wholesaler → mart →
  supermarket) are noted in `business_types.json` but explicitly NOT
  implemented — parked per the discussion.
- **Mechanic loyalty/commission arrangements** (independent mechanics
  paying a cut to a yard owner, mentioned re: auto_spares/garage) is a
  business-model/revenue-share question for a future phase, not a
  taxonomy concern — noted, not addressed here.

## What needs your review, in order of importance

1. **The 4 structural questions flagged in the first pass are now resolved**
   — see "Decisions made" above (`clothing_store` niches, animal feed
   deferred to a future `agrovet` type, M-Pesa float excluded from stock
   tracking, chang'aa/local spirits removed for now).
2. **Brand names — filled in, not yet spot-checked against real market
   reality.** All 107 slots that were `NEEDS_REVIEW` now have 1–4 suggested
   brands each (see `BRAND_DRAFT_FOR_REVIEW.md` for the full list as
   originally drafted). These are a confident first pass, not verified
   fact — worth a skim for anything that looks off, especially the items
   flagged ⚠️ in the draft (generic/weak-signal categories like
   Wheelbarrow, GI pipe, boutique footwear).
3. **Colloquial units/spellings** in `units.json` — I've guessed at a few
   (debe, gorogoro, gunia) but Kenyan market colloquialisms are exactly
   where I'm least reliable. Not yet reviewed.


## Validation already done (structural correctness, not content accuracy)

- All 13 JSON files parse correctly.
- Every `category_id`/`subcategory_id`/`unit` referenced in a template
  actually exists in the shared reference files (no dangling references).
- Every category's `used_by` list in `categories.json` matches what its
  templates actually reference, in both directions (no category claiming
  to be used by a type that doesn't reference it, and no template
  referencing a category that doesn't declare it).

None of this checks whether the *content* is right for the Kenyan market —
that's what your review is for.

## Decisions made — July 2026, second review pass

These four were open questions in the original draft; all four are now resolved:

1. **Boutique → Clothing Store.** School-uniform shops and secondhand/mitumba
   sellers are structurally different enough from a general boutique (different
   suppliers, customer relationship, seasonality) to need their own niche
   templates rather than more boutique categories. `boutique` business type is
   now `clothing_store` with a `niches` field: `boutique`, `school_uniforms`,
   `mitumba`. **Only the `boutique` niche template exists** (`templates/clothing_store.json`,
   `niche: "boutique"`) — `school_uniforms` and `mitumba` templates are declared
   but not built. Open follow-up.
2. **Animal feed → out of scope, deferred to a future `agrovet` type.**
   `Bran/animal feed by-product` removed from `cereals_grains.json`. `agrovet`
   isn't one of the 9 first-cohort types yet — adding it (with its own feed/
   veterinary/seed categories) is future Phase 8 scope, not started.
3. **M-Pesa float → resolved as excluded from stock tracking.** The kiosk
   template's `M-Pesa float` item now carries `"stock_tracking": "excluded"`
   — it's cash-equivalent, not a stocked physical item. This is a taxonomy-level
   flag only; the actual float-balance handling in the app's schema is still
   unbuilt (a later phase's concern).
4. **Chang'aa / local traditional spirits → excluded for now.** Licensing
   sensitivity unresolved — the `spirits_local_traditional` subcategory
   (Chang'aa, Muratina) was removed entirely from `bar.json` and from
   `subcategories.json`. Revisit if/when the licensing question has a real
   answer.

---



Whatever's easiest for you — edit the JSON directly, or just tell me
"remove X from hardware," "kiosk needs a Y category," "these are the real
brands for paint," etc., and I'll fold it into the files. No need to
reproduce the whole structure yourself.