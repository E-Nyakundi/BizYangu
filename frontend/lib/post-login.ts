/**
 * BizYangu — shared "where does this user land" decision.
 *
 * Every place that finishes an auth/onboarding flow (OTP login for a
 * returning user, or any of the onboarding exit points for a brand-new
 * user) should route through goToApp() instead of hardcoding
 * router.push('/dashboard'). That's what makes PIN setup actually show
 * up for first-time users on their real "first entry into the app"
 * moment, instead of only being reachable from the returning-user login
 * branch.
 *
 * IMPORTANT: neither function here trusts the `user` object it's
 * handed. Earlier versions routed off whatever the caller passed in —
 * the freshly-verified OTP response, or whatever useAuthStore happened
 * to hold at that render. That made this a relay — correct only if
 * every single thing upstream (setup, onboarding save, PIN setup) had
 * already put a fully-correct object into the store, with no stale
 * merge and no timing gap, every time. One weak link anywhere in that
 * chain and a user with a real business could get bounced back to
 * /setup. Instead, both functions always re-fetch the canonical profile
 * from the backend (GET /auth/me/) and act on *that*.
 */

import type { useRouter } from 'next/navigation'
import type { UserProfile } from './types'
import { fetchMe, useAuthStore } from './auth'
import { setPinEnabledOnDevice, setSessionUnlocked } from './device-lock'

type Router = ReturnType<typeof useRouter>

/**
 * Re-verifies with the backend and lands on /dashboard — no PIN check.
 * Used once has_pin is already known to be settled one way or another
 * (just set, or deliberately skipped) and the caller just needs to
 * actually get into the app on correct data.
 */
async function enterDashboard(router: Router): Promise<void> {
  let current: UserProfile
  try {
    current = await fetchMe()
  } catch {
    router.push('/login')
    return
  }

  useAuthStore.getState().setUser(current)

  if (current.has_pin) {
    await setPinEnabledOnDevice(true, current.name || current.phone_number)
    setSessionUnlocked(true)
  }
  router.push('/dashboard')
}

/**
 * The checkpoint used by login and every onboarding exit point: decides
 * PIN-setup vs dashboard off a fresh backend fetch, ignoring whatever
 * `user` the caller passed in.
 */
export async function goToApp(router: Router, user: UserProfile | null): Promise<void> {
  if (!user) {
    router.push('/login')
    return
  }

  let current: UserProfile
  try {
    current = await fetchMe()
  } catch {
    router.push('/login')
    return
  }

  useAuthStore.getState().setUser(current)

  if (!current.has_pin) {
    router.push('/pin/setup')
    return
  }

  await setPinEnabledOnDevice(true, current.name || current.phone_number)
  setSessionUnlocked(true)
  router.push('/dashboard')
}

/**
 * Used by the PIN setup screen itself once it's done (PIN just set, or
 * the user chose Skip / declined biometric) — goes straight to
 * /dashboard without re-checking has_pin, so Skip can't loop back to
 * /pin/setup.
 */
export async function finishPinSetup(router: Router): Promise<void> {
  await enterDashboard(router)
}
