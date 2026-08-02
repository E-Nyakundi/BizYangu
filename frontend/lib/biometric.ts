/**
 * BizYangu — biometric unlock (Face/Touch ID, Android BiometricPrompt).
 *
 * Biometric is purely client-side: there is no separate backend path.
 * All it does is gate reading the PIN back out of the OS-encrypted
 * credential store (Android Keystore / iOS Keychain, via
 * capacitor-native-biometric's setCredentials/getCredentials) before
 * calling the exact same POST /api/v1/auth/pin/verify/ a manually typed
 * PIN would call. If a device has no biometric hardware, or the plugin
 * isn't available (plain web/PWA), everything here fails soft and the
 * caller falls back to the on-screen PIN pad.
 *
 * Requires `capacitor-native-biometric` (added to package.json) — run
 * `npm install && npx cap sync android` after pulling this in.
 */

const BIOMETRIC_SERVER = 'com.bizyangu.app.pin'
const BIOMETRIC_ENABLED_KEY = 'bizyangu_biometric_enabled'

async function getPlugin() {
  const mod = await import('capacitor-native-biometric')
  return mod.NativeBiometric
}

/**
 * capacitor-native-biometric is native-only — Android Keystore / iOS
 * Keychain simply don't exist in a browser. On a real device its web
 * stub should fail fast, but that's not guaranteed for every plugin
 * (some hang instead of rejecting when there's no native bridge to
 * answer). Checking Capacitor.isNativePlatform() first means we never
 * even attempt the call on web — no plugin behavior to depend on.
 */
async function isNative(): Promise<boolean> {
  try {
    const { Capacitor } = await import('@capacitor/core')
    return Capacitor.isNativePlatform()
  } catch {
    return false
  }
}

/** Does this device have usable biometric hardware enrolled at all? */
export async function isBiometricAvailable(): Promise<boolean> {
  if (!(await isNative())) return false
  try {
    const NativeBiometric = await getPlugin()
    const result = await NativeBiometric.isAvailable()
    return !!result.isAvailable
  } catch {
    return false
  }
}

/** Has the user opted in to biometric unlock (separate from PIN itself)? */
export async function isBiometricEnabled(): Promise<boolean> {
  try {
    const { Preferences } = await import('@capacitor/preferences')
    const result = await Preferences.get({ key: BIOMETRIC_ENABLED_KEY })
    return result.value === 'true'
  } catch {
    return false
  }
}

/**
 * Turn biometric unlock on: prompts for a fingerprint/face scan to
 * confirm the sensor works, then stores the PIN behind it. Call this
 * right after the user has just set/confirmed their PIN, while it's
 * still in memory.
 */
export async function enableBiometric(pin: string): Promise<boolean> {
  if (!(await isNative())) return false
  try {
    const NativeBiometric = await getPlugin()
    await NativeBiometric.verifyIdentity({
      reason: 'Wezesha kufungua kwa alama ya kidole / uso',
      title: 'BizYangu',
    })
    await NativeBiometric.setCredentials({
      username: 'bizyangu-pin',
      password: pin,
      server: BIOMETRIC_SERVER,
    })
    const { Preferences } = await import('@capacitor/preferences')
    await Preferences.set({ key: BIOMETRIC_ENABLED_KEY, value: 'true' })
    return true
  } catch {
    return false
  }
}

/** Turn biometric unlock off and wipe the stored PIN from the Keystore/Keychain. */
export async function disableBiometric(): Promise<void> {
  if (!(await isNative())) return
  try {
    const NativeBiometric = await getPlugin()
    await NativeBiometric.deleteCredentials({ server: BIOMETRIC_SERVER })
  } catch {
    // nothing stored, or plugin unavailable — fine either way
  }
  try {
    const { Preferences } = await import('@capacitor/preferences')
    await Preferences.set({ key: BIOMETRIC_ENABLED_KEY, value: 'false' })
  } catch {
    // ignore
  }
}

/**
 * Prompts Face/Touch ID / BiometricPrompt, and on success returns the PIN
 * that was stored behind it — ready to hand straight to verifyPin().
 * Returns null on any failure (cancelled, no hardware, nothing stored)
 * so the caller can silently fall back to the manual PIN pad.
 */
export async function unlockPinWithBiometric(): Promise<string | null> {
  if (!(await isNative())) return null
  try {
    const NativeBiometric = await getPlugin()
    await NativeBiometric.verifyIdentity({
      reason: 'Thibitisha ili kuingia',
      title: 'BizYangu',
    })
    const credentials = await NativeBiometric.getCredentials({ server: BIOMETRIC_SERVER })
    return credentials.password || null
  } catch {
    return null
  }
}
