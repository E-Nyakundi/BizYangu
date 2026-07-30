# BizYangu — Production Deployment Checklist

No existing deployment checklist was found in the repo (`PHASE7_BUILD_and_PHASE9_AUDIT.md`
and the build-plan docs reference a "Phase 7 checklist" for a different, earlier
scope — pilot recruitment, not infra). This is written fresh, against the actual
code — every item below was checked against `backend/`, `frontend/`, and
`docker-compose.yml` as they exist in the current zip, not assumed.

Work top to bottom. Nothing in "Go-live" should happen before everything above it
is checked.

---

## 0. Clean database — the decision you just made

Starting production on a fresh database (not migrating dev data over) is the
right call — dev data has fake businesses, sandbox M-Pesa transactions, and
whatever test accounts accumulated during Phases 0–5. Concretely:

- [ ] Provision a **new** Postgres instance (or a new DB on existing infra) —
      don't reuse `bidness`/`lewis`/the dev password from `docker-compose.yml`.
      Generate a new random password; the current one (`M@$ter`) is dev-only and
      is sitting in plaintext in `docker-compose.yml` and `backend/.env` right now.
- [ ] Run `python manage.py migrate` against the empty DB. This is the same path
      Phase 0 already verified cleanly (`0003 → 0004_phase9_unreconciled_items →
      0005_transaction_customer`), so this should just work — but run it for real
      against the actual prod DB before anything else touches it.
- [ ] `python manage.py createsuperuser` — your first and only admin account.
      Don't carry over a dev superuser.
- [ ] **Do not** run any fixture/seed data for businesses, products, or
      transactions. The only thing that should exist after this step is an empty
      schema plus your one admin user.
- [ ] Confirm the `knowledge/` directory (business types, categories, units,
      templates — read live from JSON, not seeded into the DB) is deployed as a
      sibling of `backend/` on the production host, matching the path
      `apps/knowledge/loader.py` expects (`Path(BASE_DIR).parent / 'knowledge'`).
      This exact assumption broke once already inside Docker until the bind mount
      was added — check it explicitly on whatever platform you deploy to, don't
      assume it carries over.

---

## 1. Secrets & environment

Everything below currently has a dev/sandbox value in `backend/.env`. None of
these should be reused in production — treat this as a full rotation, not a copy:

- [ ] `SECRET_KEY` — currently the placeholder `django-insecure-change-this-in-
      production-...`. Generate a real one: `python -c "from django.core.management.utils
      import get_random_secret_key; print(get_random_secret_key())"`
- [ ] `DEBUG=False` — already set, keep it. Never flip this on in production even
      temporarily to debug something; it exposes stack traces with settings values.
- [ ] `DB_PASSWORD` — new, generated, not `M@$ter`.
- [ ] `ALLOWED_HOSTS` — currently your cloudflare tunnel domain
      (`trends-powell-guam-wal.trycloudflare.com`). Replace with your real
      production domain. Tunnel domains change on every `cloudflared` restart —
      confirm you're moving to a stable domain, not another quick tunnel.
- [ ] `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` — same swap, real domain.
- [ ] `DEV_OTP_BYPASS` — remove entirely, or set `False`. If this leaks into
      production as `True`, **anyone can log in to any phone number with
      `000000`.** This is the single highest-severity item on this whole list —
      double check it after deploy, don't just trust the `.env` file you wrote.
- [ ] `AT_USERNAME` / `AT_API_KEY` — swap sandbox (`sandbox` username) for your
      live Africa's Talking app credentials.
- [ ] `MPESA_ENV` — set to `production` (currently `sandbox`). Confirm this
      actually flips the base URL: `apps/payments/daraja.py` switches between
      `sandbox.safaricom.co.ke` and `api.safaricom.co.ke` based on this exact
      value.
- [ ] `MPESA_CONSUMER_KEY` / `MPESA_CONSUMER_SECRET` / `MPESA_SHORTCODE` /
      `MPESA_PASSKEY` — swap sandbox values (shortcode `174379` is Safaricom's
      public test till, not yours) for your real Daraja production app
      credentials.
- [ ] `MPESA_CALLBACK_URL` — must point at your real production domain, HTTPS,
      publicly reachable before you register it with Safaricom.
- [ ] `MPESA_CALLBACK_IP_ALLOWLIST_DISABLED` — currently `True` (disabled).
      Decide deliberately whether to enable Safaricom's IP allowlist for the
      callback endpoint in production; leaving it disabled is a reasonable
      pilot-stage tradeoff but should be a choice, not an oversight.
- [ ] `ADMIN_URL_PATH` — set to a long random slug (e.g.
      `xk7-manage-2f9/`). Currently defaults to `admin/`, the first path every
      bot scans.
- [ ] `SENTRY_DSN` — currently empty, meaning `sentry-sdk` is installed and
      wired in `settings/production.py` but reporting nowhere. Get a real DSN and
      set it before go-live, not after the first crash.
- [ ] `FCM_SERVICE_ACCOUNT_JSON` — decide now whether low-stock push
      notifications are in scope for pilot. If not, leave empty (the code
      degrades gracefully). If yes, this needs the full Firebase service account
      JSON as one line.

---

## 2. Backend deploy mechanics — the Dockerfile is dev-only

This is the part most likely to bite you if you deploy exactly what's in the
zip: **`backend/Dockerfile` runs `manage.py runserver`** (Django's dev server —
single-threaded, not for real traffic, no static file serving) and installs
`requirements/development.txt`, which pulls in `django-debug-toolbar`. Neither
should run in production.

- [ ] Production image/process should install `requirements/production.txt`
      (already has `gunicorn` and `sentry-sdk` — someone already planned for
      this, it's just not wired into the Dockerfile).
- [ ] Because the app uses Django Channels for WebSockets (payments status
      updates, live reports — see `CHANNEL_LAYERS` in `settings/base.py` and
      `ASGI_APPLICATION`), you need an ASGI-capable process, not plain gunicorn.
      `daphne -b 0.0.0.0 -p $PORT bizyangu.asgi:application` (what
      `docker-compose.yml`'s dev command already uses) is the straightforward
      choice — or gunicorn with a uvicorn worker class if you want gunicorn's
      process management. Pick one deliberately.
- [ ] Add `python manage.py collectstatic --noinput` to the deploy step.
      Whitenoise (`STATICFILES_STORAGE` in `settings/production.py`) serves
      `STATIC_ROOT`, which is empty until this runs — right now nothing in the
      repo runs it.
- [ ] `python manage.py migrate --noinput` on deploy (already in the compose
      command, keep it, but this is only safe *because* it's a clean DB with a
      verified migration chain — see §0).
- [ ] **`docker-compose.yml` has no Celery worker or Celery beat service at
      all**, despite `CELERY_BEAT_SCHEDULE` in `settings/base.py` scheduling the
      STK-timeout cleanup job every 5 minutes. As shipped, that job likely never
      runs unless started manually. You need two more long-running processes in
      production: `celery -A bizyangu worker` and `celery -A bizyangu beat`
      (or one combined `-B` process for a small pilot deploy — fine at this
      scale, just know it's a single point of failure for both).
- [ ] No reverse proxy / TLS termination exists in `docker-compose.yml` — if
      you're deploying to a platform (Render, Railway, Fly.io, etc.) that
      terminates HTTPS for you, this is already handled. If you're deploying to
      a bare VM, you need nginx or Caddy in front of daphne before this is
      internet-safe.

---

## 3. M-Pesa production cutover

- [ ] Confirm your Daraja **production** app is approved and live (not still
      pending Safaricom review) before pointing `MPESA_ENV=production` at it.
- [ ] Run `apps/payments/management/commands/register_c2b.py` against
      production — this command already exists in the repo for registering C2B
      validation/confirmation URLs, but it needs to be re-run against the
      production shortcode; the sandbox registration doesn't carry over.
- [ ] Do one real end-to-end STK push with a small real amount (e.g. KES 1) as
      the first production payment test, before any pilot business touches it.
- [ ] Confirm the Celery beat STK-timeout sweep (§2) is actually running in
      production — this is the safety net for exactly the kind of stuck-payment
      bug that was already fixed once in dev.

---

## 4. OTP / SMS production cutover

- [ ] `DEV_OTP_BYPASS=False` (also listed in §1 — this is the one to verify
      twice).
- [ ] Live Africa's Talking credentials in place (§1).
- [ ] Register a proper alphanumeric Sender ID with Africa's Talking (e.g.
      `BizYangu`) before pilot — this is a telco approval process that takes a
      few days, so start it early rather than the day you want to launch.
      Without it, `apps/accounts/services.py`'s `send_otp_sms()` sends from AT's
      shared default sender, which can read as generic/spammy to a first-time
      user.
- [ ] Send yourself a real OTP end-to-end after cutover — don't just trust the
      config, actually receive an SMS.

---

## 5. Frontend / APK

- [ ] `NEXT_PUBLIC_API_URL` — baked in at `next build` time, must point at your
      real production API domain, not the cloudflare tunnel.
- [ ] Rebuild the APK after that change — it won't pick up a new API URL at
      runtime, only at build time (already noted in your own `frontend/.env.local`
      comments).
- [ ] Decide and document your APK signing approach before the first real
      install — no keystore currently exists in the project (checked). Sideloaded
      APKs for a 3–5 business pilot can use a debug/self-signed key, but write
      down which one, since losing an unsigned/undocumented keystore later means
      you can't ship updates to the same app without users uninstalling first.
- [ ] One real device smoke test of the rebuilt APK against the production
      backend before handing it to a pilot business — login → sell → STK push →
      dashboard, at minimum.

---

## 6. Monitoring & backups

- [ ] **Do one real Postgres restore-from-backup test before any pilot data
      exists.** Not "backups are configured" — actually take a backup, actually
      restore it somewhere, actually confirm the data is there. This is cheap
      now and painful to discover doesn't work after a pilot business has a
      week of real sales in it.
- [ ] Confirm Sentry is actually receiving events post-deploy — trigger one
      deliberate test error and check it shows up, don't just check the DSN is
      set.
- [ ] Basic usage instrumentation — at minimum, transaction count and
      last-active timestamp per business, queryable from Django admin, so you
      can answer "did they actually use it yesterday" without asking. (This was
      already scoped in Phase 6 of the build plan; it's still open.)

---

## 7. Access & operational readiness

- [ ] Admin URL moved off `/admin/` (§1) and only you have the credentials.
- [ ] One-page install guide for a non-technical Android user: "allow unknown
      sources → install APK → open." Your pilot users are duka owners, not
      developers.
- [ ] A feedback channel (WhatsApp group with you + pilot owners was the plan)
      set up and tested before the first business goes live, not after the first
      complaint.
- [ ] Feature scope frozen at whatever ships in this deploy — no new features
      mid-pilot unless something is actively broken. (This was already a stated
      principle in Phase 7 of the build plan — repeating it here because it's
      easy to break once real usage starts generating ideas.)

---

## 8. Go-live smoke test (do this in order, on production, before real users)

1. [ ] Fresh DB migrated clean, superuser created (§0)
2. [ ] Load the app, confirm `DEBUG=False` (check that a deliberately broken
       URL shows a generic error page, not a stack trace)
3. [ ] Sign up / OTP login with a real phone number, real SMS received
4. [ ] Complete business setup / onboarding
5. [ ] Add a product, make a sale, confirm stock decrements
6. [ ] Real M-Pesa STK push for a small real amount, confirm it reaches
       `CONFIRMED` (not stuck `PENDING`)
7. [ ] Confirm the reconciliation queue, dashboard, and reports all load with
       real data from step 5–6
8. [ ] Trigger a deliberate backend error, confirm it shows up in Sentry
9. [ ] Kill and restore the DB from a backup taken after step 7, confirm data
       survives

Only after all nine pass: hand the APK to the first real pilot business.

---

## 9. Rollback plan

- [ ] Know, in writing, how you'd roll back before you need to: keep the
      previous known-good backend deploy available (previous Docker image tag or
      git commit), and take a DB backup immediately before every future deploy
      once pilot data exists — not just on a schedule.
