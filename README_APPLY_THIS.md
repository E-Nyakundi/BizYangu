# How to apply this zip

Every path in here mirrors your actual project structure — extract it
straight into your project root and let it overwrite. Example:

```bash
cd /path/to/BizYangu
unzip -o bizyangu-deploy-patch.zip -d .
```

That places everything correctly: `backend/apps/accounts/admin.py`,
`frontend/android/app/build.gradle`, `docker-compose.prod.yml` at the
root, etc.

## Two things a zip can't do — delete these yourself

1. **Stale root duplicates** (dead weight from before the backend/frontend
   split, confirmed unused):
   ```bash
   rm manage.py package.json globals.css
   ```
2. **The duplicate migration** (this exact file keeps reappearing across
   uploads — same one Phase 0 removed before):
   ```bash
   rm backend/apps/transactions/migrations/0004_transactionitem_is_reconciled_transactionitem_name_and_more.py
   ```
   Keep `0004_phase9_unreconciled_items.py` — that's the one `0005` actually
   depends on, and the only one with the data-migration backfill.

## What's in here

| Path | What it is |
|---|---|
| `.gitignore` | Corrected — no longer blanket-ignores `android/`, adds `*.jks`, `*.log` |
| `docker-compose.prod.yml`, `Caddyfile` | Production stack for the Oracle VM |
| `.env.production.example` | Template — `SECRET_KEY`/DB password/admin slug generated, rest marked `TODO` |
| `backend/Dockerfile.prod` | Production image (daphne, not `runserver`) |
| `backend/bizyangu/settings/base.py` | Adds `AT_SENDER_ID` setting |
| `backend/apps/accounts/services.py` | OTP SMS now supports a Sender ID once approved |
| `backend/apps/{accounts,transactions,payments,catalog}/admin.py` | New — User/Transaction/STK/Product visibility in Django admin |
| `frontend/android/app/build.gradle`, `.gitignore` | Wires up release signing |
| `frontend/android/app/bizyangu-release.jks`, `keystore.properties`, `KEYSTORE_README.md` | Your generated signing key — read the README before anything else |
| `BizYangu_Deployment_Checklist.md` | Full checklist, repeated here for convenience |

Everything backend-side has already been verified against a real migrated
throwaway DB (migrate clean, all four new admin pages return 200 logged
in as superuser, `collectstatic` runs against real production settings) —
not just written and assumed to work.
