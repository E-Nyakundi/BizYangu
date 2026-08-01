# BizYangu — Session Patch: PIN/biometric frontend (item 1, part 2)

Extract over your project root — paths match the real repo exactly.

## Context

The PIN backend (from the previous session's zip) is confirmed merged in the
copy you sent over — `pin_hash`/lockout fields, `pin/set/`, `pin/verify/`,
migrations, `has_pin` on the profile serializer all present and correct. No
backend changes in this patch.

This patch is the frontend half: PIN-entry screen + biometric, per the design
already agreed —
- PIN is a second factor on top of an already-valid httpOnly refresh cookie,
  never checked alone.
- Biometric is client-side only: it just gates reading the PIN back out of
  the OS-encrypted credential store (Android Keystore / iOS Keychain) before
  calling the same `pin/verify/` endpoint a typed PIN would.

## What's new

| Path | What it does |
|---|---|
| `frontend/lib/pin.ts` | Wraps `pin/set/` and `pin/verify/`; a helper distinguishes "wrong PIN" from "refresh cookie is dead — needs real OTP" so the lock screen can branch correctly |
| `frontend/lib/device-lock.ts` | Per-device "PIN lock is on" flag (Preferences-backed, survives restarts) kept separate from per-session "already unlocked" (memory-only — resets on cold start, which is the point) |
| `frontend/lib/biometric.ts` | Wraps `capacitor-native-biometric`: availability check, enable (stores PIN behind a biometric prompt), disable, and unlock-and-retrieve-PIN |
| `frontend/components/PinPad.tsx` | Reusable numeric keypad matching the existing dark/terminal design tokens |
| `frontend/components/PinLockScreen.tsx` | The actual lock screen: greets by name, auto-tries biometric if enabled, falls back to the pad, has "log in with OTP instead" |
| `frontend/app/pin/setup/page.tsx` | Post-login PIN setup: choose → confirm → optional biometric opt-in. Reachable again from Settings to change an existing PIN |

## What changed

- `frontend/app/login/page.tsx` — after OTP verify: new users/no business still
  go to `/setup` as before; existing users with no PIN yet go to `/pin/setup`;
  existing users who already have a PIN get the device lock (re-)armed and go
  straight to `/dashboard`.
- `frontend/app/(app)/layout.tsx` — **the important one.** Added a lock check
  that runs *before* `hydrate()` is allowed to fire. This matters because
  `hydrate()` calls `GET /auth/me`, and a 401 there triggers `lib/api.ts`'s
  silent access-token refresh using the still-valid refresh cookie — which
  would log the user straight back in and skip the PIN screen entirely if it
  ran first. So: check device-lock state → if locked, render
  `PinLockScreen` and don't touch `/auth/me` until it resolves → then let the
  existing guard run as before.
- `frontend/app/(app)/settings/page.tsx` — new Security card: shows whether
  quick PIN entry is on for this device, links to set/change it, a "Turn off"
  that clears the device lock and wipes any stored biometric credential, and
  a biometric row (only shown when hardware exists and a PIN is already set).
- `frontend/lib/types.ts` — added `has_pin: boolean` to `UserProfile` (already
  returned by the backend serializer, just wasn't in the frontend type).
- `frontend/lib/copy.ts` — new EN + SW strings for all of the above.
- `frontend/package.json` — added `capacitor-native-biometric@^4.2.2`.

## Run this first

```bash
npm install
npx cap sync android
```

`capacitor-native-biometric` needs the native sync step to pull in the
Android BiometricPrompt / iOS LocalAuthentication bindings before an APK
build will actually have the plugin.

## How I verified it

No `node_modules` in the zip you sent, so I installed a full local copy and
ran `npx tsc --noEmit` against the whole project — clean, no errors. I also
tried a full `next build`, but the sandbox's network allowlist blocks
`fonts.googleapis.com` (your `layout.tsx` pulls Space Grotesk / JetBrains Mono
at build time), so the production build itself couldn't complete here — that
part is untested end-to-end. Worth a real `npm run build` on your machine
before you consider this done. I did not have a live backend to hit for a
real HTTP round-trip test of `pin/verify/` from this new frontend code.

## Still open from the pre-pilot checklist

Everything else from item 1 down: branding sweep for stray "LN Systems",
M-Pesa till/paybill sync (customer-facing and subscription), payments data in
Reports, onboarding taxonomy → brand drill-down, biasharasystems.co.ke company
site, PWA installability. Plus the still-open infra items: Vercel Production
Branch fix, Oracle Ampere/Always-Free migration before trial credit runs out,
Africa's Talking live (non-sandbox) credentials, and the hardcoded
`localhost:3000` in the staff invite link.
