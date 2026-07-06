/**
 * BizYangu — Theme management (light/dark).
 *
 * Persists theme preference to native storage (Capacitor Preferences)
 * with localStorage fallback for web dev. Uses the same pattern as
 * lib/offline-queue.ts to avoid breaking on Capacitor WebView.
 */

const THEME_KEY = 'bizyangu_theme'
const THEME_ROOT = 'html' // DOM element to set [data-theme] on

export type Theme = 'light' | 'dark'

/**
 * Get current theme from storage, default to dark.
 * Tries Preferences first (native), falls back to localStorage.
 */
export async function getTheme(): Promise<Theme> {
  try {
    // Try Capacitor Preferences first (mobile app)
    const { Preferences } = await import('@capacitor/preferences')
    const result = await Preferences.get({ key: THEME_KEY })
    if (result.value) {
      return (result.value as Theme) || 'dark'
    }
  } catch {
    // Capacitor not available (web, or failed) — continue to localStorage
  }

  // Fallback to localStorage for web dev / Preferences unavailable
  if (typeof window !== 'undefined' && window.localStorage) {
    const stored = window.localStorage.getItem(THEME_KEY)
    if (stored === 'light' || stored === 'dark') {
      return stored
    }
  }

  return 'dark'
}

/**
 * Set theme and persist to storage.
 * Applies [data-theme] to root element immediately (no paint flash).
 */
export async function setTheme(theme: Theme) {
  // Apply immediately to avoid flash
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', theme)
  }

  // Persist
  try {
    const { Preferences } = await import('@capacitor/preferences')
    await Preferences.set({ key: THEME_KEY, value: theme })
  } catch {
    // Preferences unavailable (web) — use localStorage
  }

  if (typeof window !== 'undefined' && window.localStorage) {
    window.localStorage.setItem(THEME_KEY, theme)
  }
}

/**
 * Toggle between light and dark modes.
 */
export async function toggleTheme() {
  const current = await getTheme()
  const next = current === 'dark' ? 'light' : 'dark'
  await setTheme(next)
  return next
}

/**
 * Initialize theme on app mount.
 * Should be called in app/layout.tsx or similar root layout.
 * Returns the applied theme.
 */
export async function initializeTheme(): Promise<Theme> {
  const theme = await getTheme()
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', theme)
  }
  return theme
}
