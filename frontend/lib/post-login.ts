/**
 * BizYangu — shared "where does this user land" decision.
 *
 * Every place that finishes an auth/onboarding flow (OTP login for a
 * returning user, or any of the onboarding exit points for a brand-new
 * user) should route through this instead of hardcoding
 * router.push('/dashboard'). That's what makes PIN setup actually show
 * up for first-time users on their real "first entry into the app"
 * moment, instead of only being reachable from the returning-user login
 * branch.
 *
 * Logic: if the account has no PIN yet, send it to set one up. If it
 * already has a PIN, this device is now "authenticated for this
 * session" — arm the device lock (so the next cold start shows the
 * lock screen) and mark the session unlocked (so we don't immediately
 * re-prompt for the PIN we just implicitly satisfied via OTP/onboarding).
 *
 * `user` is typed nullable because some call sites (onboarding) read it
 * from useAuthStore, which is UserProfile | null until hydrated. In
 * practice goToApp is only ever called once a user is known to exist
 * (post-OTP, post-onboarding-save) — null here means something upstream
 * is wrong, so we fail safe back to login rather than guessing at PIN
 * state.
 */

import type { useRouter } from 'next/navigation'
import type { UserProfile } from './types'
import { setPinEnabledOnDevice, setSessionUnlocked } from './device-lock'

type Router = ReturnType<typeof useRouter>

export async function goToApp(router: Router, user: UserProfile | null): Promise<void> {
  if (!user) {
    router.push('/login')
    return
  }

  if (!user.has_pin) {
    router.push('/pin/setup')
    return
  }

  await setPinEnabledOnDevice(true, user.name || user.phone_number)
  setSessionUnlocked(true)
  router.push('/dashboard')
}
