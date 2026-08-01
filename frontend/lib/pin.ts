/**
 * BizYangu — PIN quick re-entry API calls.
 *
 * A PIN is a second factor layered on an already-valid httpOnly refresh
 * cookie — see backend/apps/accounts/views.py (pin_set / pin_verify).
 * It is never checked on its own: pin_verify reads the same refresh
 * cookie token_refresh uses, so a device without a prior OTP login can't
 * use a stolen/guessed PIN for anything.
 *
 * This file only wraps the two endpoints. Device-level state (whether
 * quick PIN entry is turned on for this device, whether biometric is
 * enabled) lives in lib/device-lock.ts and lib/biometric.ts.
 */

import { api, apiErrorMessage } from './api'
import type { UserProfile } from './types'

export interface PinVerifyResult {
  user: UserProfile
}

export interface PinVerifyError {
  detail: string
  attemptsRemaining?: number
  /** True when the refresh cookie itself is gone/invalid — no amount of
   *  retrying the PIN will help; the device needs a full OTP login. */
  sessionDead: boolean
}

/**
 * POST /api/v1/auth/pin/set/
 * Requires a valid (fresh) access token — call right after OTP login,
 * or from Settings while already signed in.
 */
export async function setPin(pin: string): Promise<string> {
  const { data } = await api.post('/auth/pin/set/', { pin })
  return data.detail as string
}

/**
 * POST /api/v1/auth/pin/verify/
 * No access token needed — reads the refresh cookie. On success, rotates
 * cookies and returns the user profile, exactly like OTP verify does.
 */
export async function verifyPin(pin: string): Promise<PinVerifyResult> {
  const { data } = await api.post('/auth/pin/verify/', { pin })
  return data as PinVerifyResult
}

/**
 * Normalizes the various pin/verify failure shapes (wrong PIN with
 * attempts remaining, locked out, session expired/invalid) into one
 * object the lock screen can branch on without repeating axios plumbing.
 */
export function pinVerifyErrorInfo(err: unknown): PinVerifyError {
  const status = (err as { response?: { status?: number } })?.response?.status
  const data = (err as { response?: { data?: Record<string, unknown> } })?.response?.data
  const attemptsRemaining =
    typeof data?.attempts_remaining === 'number' ? (data.attempts_remaining as number) : undefined

  // 401 with no attempts_remaining field means the refresh cookie was
  // missing/expired/invalid — not a wrong PIN. Only a real OTP login can
  // recover from this, so the caller should clear device PIN state.
  const sessionDead = status === 401 && attemptsRemaining === undefined

  return {
    detail: apiErrorMessage(err),
    attemptsRemaining,
    sessionDead,
  }
}
