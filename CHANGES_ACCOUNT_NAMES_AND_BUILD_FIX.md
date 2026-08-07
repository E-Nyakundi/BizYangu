# Account names/email + Vercel build fix — changes

## Reconnaissance summary

The recovered zip was further along than `pre-pilot-build-main.md` showed for
the "user only recognizable by number and title" backlog item:

- `User` model already had `first_name`/`last_name`/`email` fields, with
  `save()` deriving the legacy `name` field from them — **but no migration
  had ever been generated.**
- `UserProfileSerializer`/`UserUpdateSerializer` were never updated to
  expose/accept the new fields — this is what broke your Vercel build
  (`Property 'first_name' does not exist on type 'UserProfile'`), because the
  **frontend** (`lib/auth.ts`, the Settings account form, `/join`'s
  name-capture step) was already fully wired against fields the backend
  serializer didn't send and the frontend `UserProfile` type didn't declare.
- Reports page icon consistency (Daily/Period/Growth/Products/Losses vs.
  Payments/Creditors) — **already done** by the earlier session. No changes
  needed there.
- The owner "About you" step (name + email during `/setup`) — referenced in
  a code comment as if it existed, but was **not actually built**.

## What changed

### Backend
- `apps/core/messages.py` — added `FIRST_NAME_REQUIRED`, `LAST_NAME_REQUIRED`,
  `EMAIL_ALREADY_IN_USE`, `INVALID_EMAIL_FORMAT`, `ACCOUNT_UPDATED` (English +
  Swahili).
- `apps/accounts/serializers.py`:
  - `UserProfileSerializer` now returns `first_name`/`last_name`/`email`.
  - `UserUpdateSerializer` now accepts `first_name`/`last_name`/`email`, with
    case-insensitive email-uniqueness validation (excluding the current
    user) returning a real `MESSAGES` string instead of DRF's default.
- **New migration**: `apps/accounts/migrations/0005_user_email_user_first_name_user_last_name.py`
  — the fields existed on the model but were never migrated. Generated
  properly via `makemigrations` (not hand-written) and verified with a full
  `migrate` against a clean sqlite DB.
- **Deleted** `apps/transactions/migrations/0004_transactionitem_is_reconciled_transactionitem_name_and_more.py`
  — the same stray duplicate migration the build-plan doc says was already
  resolved had crept back into this recovered zip. Confirmed unapplied
  (`[ ]` in `showmigrations`, all its fields already defined by
  `0004_phase9_unreconciled_items`/`0007`), so deleting it was safe — no
  fake-apply or data reconciliation needed.
- Verified: `manage.py check` clean, `makemigrations --check --dry-run`
  clean, full `migrate` runs clean end-to-end, and a shell-level functional
  test confirmed name derivation, serializer output, and duplicate-email
  rejection all work correctly.

### Frontend
- `lib/types.ts` — added `first_name`/`last_name`/`email` to `UserProfile`.
  **This is the direct fix for the reported build failure.**
- `lib/copy.ts` — added ~25 missing `COPY`/`COPY_SW` keys that the
  already-built Settings account form and `/join` name-capture step
  referenced but were never defined (would have been the *next* build
  failure once the type error was fixed).
- `app/setup/page.tsx` — added a new first step, **"About you"**: the owner
  enters first name, last name, and an optional email before business setup
  continues (now 4 screens instead of 3). Calls `updateMe()` and syncs the
  auth store immediately so the name shows up correctly for the rest of
  setup and onboarding. Confirmation screen now also shows the owner's name.

## Verification

- `tsc --noEmit` — **clean, zero errors** (confirms the reported compile
  error is fixed).
- `npm run build` — compiles and typechecks cleanly; the only failure in
  this sandbox is `next/font` unable to reach `fonts.googleapis.com`
  (no internet access in this environment) — unrelated to the fix and will
  not occur on Vercel.
- Backend: `manage.py check`, `makemigrations --check`, full `migrate`, and
  a functional shell test all passed.

## Not done in this pass

- Swahili phrase accuracy pass on the new copy (draft translations added,
  same as existing pattern — still "on you" per the source doc).
- C12 (pack-size restocking) — still needs your decisions before it's built,
  per the source doc.
