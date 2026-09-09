/**
 * BizYangu — Google sign-in.
 *
 * Two completely different flows produce the same thing (a Google ID
 * token), which is then POSTed to /api/v1/auth/google/ exactly the same
 * way regardless of platform — see lib/auth.ts's googleSignIn().
 *
 * - Native (installed APK, Capacitor.isNativePlatform() === true):
 *   uses @codetrix-studio/capacitor-google-auth, which drives the real
 *   native Google Sign-In SDK (an actual system account picker, not a
 *   web view). This is required, not optional — Google's own web
 *   Identity Services flow below detects it's running inside an
 *   embedded WebView and refuses with "disallowed_useragent". There is
 *   no way to make the web flow work inside the Capacitor shell.
 *
 * - Web (browser, Capacitor.isNativePlatform() === false): uses Google
 *   Identity Services' One Tap / button flow, loaded from
 *   accounts.google.com/gsi/client. This only ever runs in a real
 *   browser tab, so the disallowed_useragent problem doesn't apply.
 *
 * Same pattern as lib/biometric.ts and lib/device-lock.ts: check
 * isNativePlatform() first, dynamic-import the native plugin only when
 * actually native, fail soft into a caller-visible error otherwise.
 */

const GOOGLE_CLIENT_ID_WEB = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID_WEB ?? ''
const GOOGLE_CLIENT_ID_ANDROID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID_ANDROID ?? ''

async function isNative(): Promise<boolean> {
  try {
    const { Capacitor } = await import('@capacitor/core')
    return Capacitor.isNativePlatform()
  } catch {
    return false
  }
}

// ── Native (Capacitor / Android) ────────────────────────────────────────────

let nativeInitialized = false

async function signInNative(): Promise<string> {
  const { GoogleAuth } = await import('@codetrix-studio/capacitor-google-auth')

  if (!nativeInitialized) {
    // clientId here is the ANDROID OAuth client (must match the SHA-1
    // fingerprint registered in Google Cloud Console for this keystore —
    // see BizYangu_Deployment_Checklist.md). serverClientId is the WEB
    // client — the plugin needs it to actually mint an idToken our
    // Django backend can verify; without it Android hands back a
    // sign-in result with no idToken at all.
    await GoogleAuth.initialize({
      clientId: GOOGLE_CLIENT_ID_ANDROID,
      scopes: ['profile', 'email'],
      grantOfflineAccess: false,
    })
    nativeInitialized = true
  }

  const result = await GoogleAuth.signIn()
  const idToken = result?.authentication?.idToken
  if (!idToken) {
    throw new Error('Google sign-in did not return an ID token.')
  }
  return idToken
}

// ── Web (Google Identity Services) ──────────────────────────────────────────

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string
            callback: (response: { credential: string }) => void
          }) => void
          prompt: () => void
          renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void
        }
      }
    }
  }
}

let gisScriptLoaded: Promise<void> | null = null

function loadGisScript(): Promise<void> {
  if (gisScriptLoaded) return gisScriptLoaded
  gisScriptLoaded = new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load Google Identity Services.'))
    document.head.appendChild(script)
  })
  return gisScriptLoaded
}

/**
 * Renders Google's own branded button into `container` and resolves
 * with an ID token once the user completes sign-in through it. Using
 * Google's rendered button (rather than a custom button that calls
 * `prompt()`) avoids One Tap's stricter UX requirements and matches
 * what Google's ToS expects for a "Continue with Google" entry point.
 */
async function signInWeb(container: HTMLElement): Promise<string> {
  await loadGisScript()

  return new Promise((resolve, reject) => {
    if (!window.google?.accounts?.id) {
      reject(new Error('Google Identity Services unavailable.'))
      return
    }
    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID_WEB,
      callback: (response) => {
        if (response?.credential) {
          resolve(response.credential)
        } else {
          reject(new Error('Google sign-in was cancelled or returned no credential.'))
        }
      },
    })
    window.google.accounts.id.renderButton(container, {
      type: 'standard',
      theme: 'filled_black',
      size: 'large',
      width: container.clientWidth || 320,
      text: 'continue_with',
    })
  })
}

// ── Public entry point ───────────────────────────────────────────────────────

export interface GoogleSignInHandle {
  /** True on native — caller should show its own trigger button. */
  isNative: boolean
  /**
   * Native: call this directly from a button's onClick — resolves with
   * the ID token once the native picker completes.
   * Web: not used directly — call mountWebButton instead, since GIS
   * needs to render its own button into the DOM up front rather than
   * being triggered imperatively from an arbitrary click handler.
   */
  signIn: () => Promise<string>
  /** Web only: renders Google's button into the given element. */
  mountWebButton: (container: HTMLElement) => Promise<string>
}

export async function getGoogleSignIn(): Promise<GoogleSignInHandle> {
  const native = await isNative()
  return {
    isNative: native,
    signIn: native ? signInNative : () => Promise.reject(new Error('Use mountWebButton on web.')),
    mountWebButton: native
      ? () => Promise.reject(new Error('mountWebButton is web-only.'))
      : signInWeb,
  }
}
