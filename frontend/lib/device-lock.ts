/**
 * BizYangu — device-level PIN lock state.
 *
 * Two different things are tracked here, both non-sensitive (no PIN or
 * token ever lives in this storage — see lib/biometric.ts for the one
 * secure-storage exception):
 *
 * 1. Whether THIS device should show the PIN lock screen on launch.
 *    Persisted via Capacitor Preferences (falls back to localStorage on
 *    web, same pattern as lib/theme.ts) so it survives app restarts.
 *
 * 2. Whether the PIN has already been entered for the CURRENT app
 *    session. Kept in sessionStorage/memory only, on purpose — that's
 *    what makes this "quick re-entry" rather than "enter once, never
 *    again": a fresh cold start (or closed tab) should re-lock.
 */

const PIN_ENABLED_KEY = 'bizyangu_pin_enabled'
const LOCK_DISPLAY_NAME_KEY = 'bizyangu_lock_display_name'

let sessionUnlocked = false

async function prefsGet(key: string): Promise<string | null> {
  try {
    const { Preferences } = await import('@capacitor/preferences')
    const result = await Preferences.get({ key })
    if (result.value !== null && result.value !== undefined) return result.value
  } catch {
    // Capacitor not available — fall through to localStorage
  }
  if (typeof window !== 'undefined' && window.localStorage) {
    return window.localStorage.getItem(key)
  }
  return null
}

async function prefsSet(key: string, value: string): Promise<void> {
  try {
    const { Preferences } = await import('@capacitor/preferences')
    await Preferences.set({ key, value })
  } catch {
    // fall through
  }
  if (typeof window !== 'undefined' && window.localStorage) {
    window.localStorage.setItem(key, value)
  }
}

async function prefsRemove(key: string): Promise<void> {
  try {
    const { Preferences } = await import('@capacitor/preferences')
    await Preferences.remove({ key })
  } catch {
    // fall through
  }
  if (typeof window !== 'undefined' && window.localStorage) {
    window.localStorage.removeItem(key)
  }
}

/** Has this device been set up to lock behind a PIN/biometric? */
export async function isPinEnabledOnDevice(): Promise<boolean> {
  return (await prefsGet(PIN_ENABLED_KEY)) === 'true'
}

/** Turn the device lock screen on/off. Also clears the current-session
 *  unlock flag so toggling never leaves the app in an inconsistent state. */
export async function setPinEnabledOnDevice(enabled: boolean, displayName?: string): Promise<void> {
  if (enabled) {
    await prefsSet(PIN_ENABLED_KEY, 'true')
    if (displayName) await prefsSet(LOCK_DISPLAY_NAME_KEY, displayName)
    sessionUnlocked = true // whoever just enabled it is already authenticated
  } else {
    await prefsRemove(PIN_ENABLED_KEY)
    await prefsRemove(LOCK_DISPLAY_NAME_KEY)
    sessionUnlocked = false
  }
}

/** Name/phone to greet with on the lock screen, e.g. "Karibu, Asha". */
export async function getLockDisplayName(): Promise<string | null> {
  return prefsGet(LOCK_DISPLAY_NAME_KEY)
}

/** Has the PIN already been entered once during this running app session? */
export function isSessionUnlocked(): boolean {
  return sessionUnlocked
}

export function setSessionUnlocked(unlocked: boolean): void {
  sessionUnlocked = unlocked
}
