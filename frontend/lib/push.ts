/**
 * BizYangu — push notification registration.
 *
 * Wraps @capacitor/push-notifications. On native (Android), this asks
 * for permission and registers an FCM token with the backend so
 * low-stock alerts can reach the device. In a plain web browser
 * (during `next dev`), the Capacitor plugin isn't present — every
 * call here fails silently, which is the correct behaviour: push just
 * isn't available on web, not an error.
 */

import { api } from './api'

const LAST_TOKEN_KEY = 'bizyango:last_push_token'

async function getStoredToken(): Promise<string | null> {
  try {
    const { Preferences } = await import('@capacitor/preferences')
    const { value } = await Preferences.get({ key: LAST_TOKEN_KEY })
    return value
  } catch {
    return null
  }
}

async function setStoredToken(token: string): Promise<void> {
  try {
    const { Preferences } = await import('@capacitor/preferences')
    await Preferences.set({ key: LAST_TOKEN_KEY, value: token })
  } catch {
    /* web — nothing to persist */
  }
}

/**
 * Call once after login / on app mount. Requests push permission (if
 * not already granted or denied), registers with FCM, and sends the
 * resulting token to the backend. Safe to call repeatedly — Capacitor
 * no-ops if already registered, and the backend registration endpoint
 * is an upsert.
 */
export async function registerPushNotifications(): Promise<void> {
  let PushNotifications: typeof import('@capacitor/push-notifications').PushNotifications
  try {
    ;({ PushNotifications } = await import('@capacitor/push-notifications'))
  } catch {
    return // Not running inside the native shell — nothing to do.
  }

  try {
    let permStatus = await PushNotifications.checkPermissions()
    if (permStatus.receive === 'prompt') {
      permStatus = await PushNotifications.requestPermissions()
    }
    if (permStatus.receive !== 'granted') {
      return // User declined — respect it, don't nag every page load.
    }

    await PushNotifications.register()

    // The 'registration' event fires once Android/FCM hands back a
    // token. We listen once per app session; registerDevice() below
    // does the actual upsert to the backend.
    PushNotifications.addListener('registration', async (token) => {
      await registerDevice(token.value, 'ANDROID')
    })

    PushNotifications.addListener('registrationError', (err) => {
      console.warn('Push registration error:', err)
    })
  } catch (err) {
    console.warn('Push notification setup failed:', err)
  }
}

async function registerDevice(token: string, platform: 'ANDROID' | 'IOS' | 'WEB'): Promise<void> {
  try {
    await api.post('/notifications/devices/', { token, platform })
    await setStoredToken(token)
  } catch {
    // Non-fatal — the app works fine without push, just no low-stock alerts.
  }
}

/**
 * Call on logout so a handed-over or shared device stops receiving
 * pushes for the account that just signed out.
 */
export async function unregisterPushNotifications(): Promise<void> {
  const token = await getStoredToken()
  if (!token) return
  try {
    await api.post('/notifications/devices/unregister/', { token })
  } catch {
    /* best effort */
  }
}
