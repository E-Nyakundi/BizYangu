# Quick fixes — Aug 7

Three files changed, one file deleted, two things to do manually
(deploy script + the live VM env file aren't in this working copy).

## 1. `knowledge/units.json` — sync with the model layer
Removed `debe_20l` (no longer a valid `Product.Unit` choice — this was
the one place the debe removal hadn't been applied; the backend model
and `frontend/lib/knowledge.ts` were already correct). Updated the
`gorogoro` label to drop the old baked-in "~2kg" to match the other
two sources. Also trimmed the now-stale `_notes` line that referenced
debe/20L-tin synonym resolution.
Drop-in replace: `knowledge/units.json`.

## 2. Staff invite link generating `localhost:3000` — root cause found
This wasn't a code bug. `backend/apps/accounts/views.py` already reads
`FRONTEND_URL` from settings (falling back to localhost only in dev),
and `backend/bizyangu/settings/production.py` already *requires*
`FRONTEND_URL` with no default — so production genuinely can't start
without it being set. The actual gap: **`FRONTEND_URL` was never
listed in either example env file**, so it's very plausible it was
never added to the real `.env.production` on the VM either, or it
still had `http://localhost:3000` left in it from local testing.
Added the missing line to both `env.production.example` and
`.env.production.example`:
```
FRONTEND_URL=https://app.biasharasystems.co.ke
```
**Action needed from you (I can't reach the VM):** SSH in and check
`.env.production` for a `FRONTEND_URL` line. Set it to
`https://app.biasharasystems.co.ke` (or whatever the real deployed
frontend domain is once Vercel's `app.` subdomain is live), then
redeploy so the container picks it up.

## 3. Stray duplicate migration — deleted
Deleted `backend/apps/transactions/migrations/0004_transactionitem_is_reconciled_transactionitem_name_and_more.py`
from this working copy. Confirmed it was never applied anywhere
(the real chain runs through `0004_phase9_unreconciled_items.py`,
which `0005_transaction_customer.py` correctly depends on) — same
stray file that's recurred in earlier zips and was already deleted
on the VM and in the git repo. No code diff to ship for this one;
just don't let it creep back into future working copies.

## 4. Redundant manual `migrate` step in the deploy routine
`Dockerfile.prod` already runs `migrate --noinput` on every container
start, so a separate manual `docker compose exec backend python
manage.py migrate` step in `deploy.ps1` (and/or the
`.github/workflows/deploy.yml` GitHub Actions step, if it has one) is
redundant and can race against the container's own auto-migrate.
**Neither file is in this uploaded zip** — they live only in the
`E-Nyakundi/BizYangu` git repo, so this one needs a manual edit on
your side: open `deploy.ps1`, remove the line running
`manage.py migrate` after `up -d --build`, keep the `build` + `up -d`
step only.
