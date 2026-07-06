/**
 * BizYangu — auth API calls + lightweight client auth store.
 * Tokens live in httpOnly cookies (see lib/api.ts). This store only
 * holds the user profile in memory for UI state (nav, gating, etc).
 */

import { create } from 'zustand'
import { api, apiErrorMessage } from './api'
import type { UserProfile } from './types'

// ── API calls ────────────────────────────────────────────────────────────────

export async function requestOtp(phoneNumber: string): Promise<string> {
  const { data } = await api.post('/auth/otp/request/', { phone_number: phoneNumber })
  return data.detail as string
}

export async function verifyOtp(
  phoneNumber: string,
  otp: string
): Promise<{ user: UserProfile; is_new_user: boolean }> {
  const { data } = await api.post('/auth/otp/verify/', { phone_number: phoneNumber, otp })
  return data
}

export async function fetchMe(): Promise<UserProfile> {
  const { data } = await api.get('/auth/me/')
  return data
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout/')
}

export { apiErrorMessage }

// ── Auth store ───────────────────────────────────────────────────────────────

interface AuthState {
  user: UserProfile | null
  isLoading: boolean
  isInitialized: boolean
  setUser: (user: UserProfile | null) => void
  hydrate: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  isInitialized: false,
  setUser: (user) => set({ user }),
  hydrate: async () => {
    set({ isLoading: true })
    try {
      const user = await fetchMe()
      set({ user, isLoading: false, isInitialized: true })
    } catch {
      set({ user: null, isLoading: false, isInitialized: true })
    }
  },
}))
