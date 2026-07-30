# BizYangu — Phase 6 Audit Findings (Sessions/JWT/Redis/N+1)
**Session: July 2026 — infrastructure audit, no product decisions involved.**

Per `BizYangu_Build_Plan_v3.md` Phase 6. Everything below was found and fixed
this session, each confirmed with a real before/after test — not just read
and assumed correct.

## 1. N+1 queries — two found, both fixed

- **`/transactions/` list + `/transactions/{id}/` detail** — `TransactionSerializer.created_by_name`
  reads `created_by.name`, and `get_refunded_amount()` ran a fresh
  `.aggregate()` query per row. Neither was covered by the existing
  `prefetch_related('items__product')`. Fixed with `select_related('created_by')`
  plus a queryset-level `annotate(refunded_total=Sum(...))`, with the
  serializer preferring the annotation and falling back to the live query
  only for un-annotated callers.
  **Proven, not assumed:** a 30-row page across 5 distinct staff members
  took **74 queries** before the fix, **4 queries** after. (Detail view: 3
  either way, since it's a single object — the fix mostly matters for lists.)
- **`/reports/losses/`** — `_loss_by_employee()` reads `m.created_by.name`
  on a queryset that only had `select_related('product')`. Added
  `'created_by'` to the same select_related.
  **Proven:** 10 loss/damage movements across 5 creators took **11 queries**
  before, **1 query** after.

Both regressions were reproduced by temporarily reverting the fix, rerunning
the same test, confirming the query count blew up, then restoring the fix —
this wasn't a "should be fine" read, the before/after numbers are real.

## 2. JWT rotation & blacklist — confirmed working, not just configured

`rest_framework_simplejwt.token_blacklist` is installed and both
`token_refresh` and `logout` call `.blacklist()` on the outgoing token
before issuing a new one. Verified functionally: rotated a refresh token,
confirmed the *old* token is rejected (401) if reused, logged out with a
fresh token, confirmed *that* token is also rejected afterward. No changes
needed here — this was already correct, now it's verified rather than
assumed.

## 3. Redis / cache — one real gap found and fixed

**`CACHES` was never configured anywhere in the settings tree.** Channels
(`CHANNEL_LAYERS`) and Celery (`CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`)
both correctly point at `REDIS_URL` — but Django's own cache framework had
no `CACHES` setting at all, which means it silently fell back to the
default `LocMemCache`: per-process, in-memory, **not shared across worker
processes**.

This matters because every DRF throttle — `OTPRateThrottle`, and the
`UserRateThrottle`/`AnonRateThrottle`/`burst_write` scope added in the
security-hardening session — tracks its request counts through Django's
cache. With `LocMemCache`, a "300/minute per user" limit was actually
"300/minute per user, *per gunicorn worker process*" — silently multiplied
by however many workers run in production. A single logical rate limit was
never actually being enforced as one.

**Fix:** `CACHES` now points at the same Redis instance already used for
Channels/Celery (`django.core.cache.backends.redis.RedisCache`, native to
Django 5.1, no new dependency needed). No new `.env` variable required —
reuses the existing `REDIS_URL`.

**Proven, not assumed:** hit the OTP endpoint 4 times rapidly for the same
phone number — attempts 1–3 succeeded, attempt 4 correctly returned `429`
with the cache-backed throttle actually enforcing the `3/hour` limit. A
second, different phone number was unaffected, confirming per-key scoping
also works correctly.

**Practical implication for you:** if your current dev/staging setup isn't
actually running Redis yet, `CACHES` will now fail on first cache access the
same way Channels/Celery already would — this isn't a new dependency, it
surfaces a pre-existing one. If Redis is already running for
Channels/Celery in your environment, this needs nothing else from you.

## What this phase did NOT touch

No product/UI decisions were made or needed — this was purely "does the
infrastructure we already built actually work the way it's supposed to."
Build Plan v3's Phase 7 onward (reports/graphs, knowledge base curation,
etc.) is unaffected and unstarted.
