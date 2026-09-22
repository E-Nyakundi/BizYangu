# Web-Search Barcode Discovery — Implementation

Implements `barcode-webcrawl-resolution-scoping.md` in full. All three
acceptance-test barcodes from §6 verified against the real evidence in
§3 (see "Verified against" below).

## Drop-in files (new — no manual edits needed)
- `apps/products/webcrawl.py` — the pipeline: search, pre-fetch scoring,
  selective fetch, extraction (aggregator-row + generic OG/JSON-LD),
  reconciliation with domain-collapse + retailer-weighting.
- `apps/products/tasks.py` — `discover_barcode_via_web` Celery task.
  Idempotent (no-op if a GlobalProduct already exists by run time).
- `apps/products/models_external_source.py` — the `ExternalSource`
  reliability-tracking model (design doc §4.7).
- `apps/products/migrations/0002_web_search_discovery.py` — migration
  for `ExternalSource` + `GlobalProduct.web_sources` M2M.

## Files requiring a hand-applied patch (existing files with history)
- `models_patch.py` → edits to `apps/products/models.py` — **applied 2026-09-22.**
- `views_patch.py` → edits to `apps/products/views.py` — already applied.
- `admin_patch.py` → edits to `apps/products/admin.py` — **applied 2026-09-22.**

Each is a `PATCH NOTES` doc, not code to import — the described edit
was applied directly to the target file rather than importing these.

**2026-09-22 — drift found and fixed:** `models_patch.py` and
`admin_patch.py` had NOT actually been applied despite migration
`0002_web_search_discovery` (which creates the `ExternalSource` table
and `GlobalProduct.web_sources` M2M column) already having run in
production. This was live-breaking, not dormant: `tasks.py`'s
`gp.web_sources.add(source)` call raised `AttributeError` on every
run of `discover_barcode_via_web` (dispatched from `resolve_barcode()`
on every UNRESOLVED scan), and `ExternalSource` had no admin
registration. Both patches are now applied for real — no new
migration was needed, since the underlying columns already existed;
this was purely model/admin code catching up to a schema that was
already live. Caught via Django's `migrate` startup check flagging
`models(customers, messaging, products)` as having changes not
reflected in a migration; `messaging` was a false positive (its
model matches its migration exactly) — the real drift was confined to
`customers.Customer.updated_at` (same category of bug, unrelated app,
fixed the same session) and this file's two patches.

## Settings / env
Add to `bizyangu/settings/base.py` (see `views_patch.py`'s second half
for the exact block) and to `requirements/base.txt`'s existing env
files:
```
GOOGLE_CSE_API_KEY=
GOOGLE_CSE_ENGINE_ID=
```
Blank-safe: an unconfigured environment logs a warning and the pipeline
degrades to `UNRESOLVED`-only, matching pre-existing behavior exactly.

`requests` is already in `requirements/base.txt` — no new dependency.

## Trust boundary (non-negotiable, per §4.5)
`_create_web_candidate()` in `tasks.py` only ever creates
`Status.CANDIDATE` with `Source.WEB_SEARCH`. It never touches
`Status.VERIFIED`. The existing `services.record_verification()` /
`CONFIRMATIONS_REQUIRED` loop is untouched and remains the only path to
VERIFIED.

## Verified against design doc §6
Ran the scoring/reconciliation logic standalone against the real
result data recorded in §3:
- **Case 3.1** (Vaseline, 8 results, 5 noise): only the 2
  `barcode-list.com` rows + 1 Scribd SKU/price hit cleared
  `MIN_SCORE_TO_FETCH`; pet listing/property/teapot/Wikimedia/orchestra
  video all scored 0 and were excluded — matches §3.1's evidence.
- **Case 3.2** (Festivita bread): 6 `barcode-list.com` hits collapsed
  into exactly 1 vote (not 6), `cleanshelf.online`'s retailer hit
  (weight 3) correctly outweighs the aggregator consensus (weight 1)
  and both domains survive into the final candidate — matches §4.4's
  requirement.
- **Case 3.3** (20-digit non-GTIN): rejected at the GTIN pre-check
  *and independently* at the scorer (0 results would clear threshold)
  — both mechanisms verified to catch it per §6's instruction that
  either failing silently would be easy to miss without the other.

## Deliberately not built this pass (per design doc §5 non-goals)
No change to `resolve_barcode()`'s sync contract/response shape, no
"search in progress" UI state, no `google.com/search` scraping, no
second search provider, no per-retailer scrapers.

## Open questions carried forward (§7 — still open, not resolved here)
- `ExternalSource.hits_confirmed`/`hits_disputed` are defined but not
  yet wired to update — that requires `services.record_verification()`
  to know how to walk a resolved `GlobalProduct`'s `web_sources` M2M
  and bump the right domains' counters when status flips to
  VERIFIED/DISPUTED. Left as a follow-up so this pass's diff stays
  reviewable — the field exists and is populated at candidate-creation
  time, ready for that wiring.
- Whether `MIN_SCORE_TO_FETCH` should move to `.env` for tuning without
  a deploy (currently a module constant, matching `CONFIRMATIONS_REQUIRED`'s
  style in `services.py`) — left as-is per §7, no decision forced.
