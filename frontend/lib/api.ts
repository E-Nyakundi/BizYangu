/**
 * BizYangu — API client
 * Axios instance using httpOnly cookie auth (set by the Django backend).
 * No tokens are read or stored in JS — the browser sends cookies automatically.
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true, // sends/receives the httpOnly access/refresh cookies
  headers: {
    'Content-Type': 'application/json',
    // Skips ngrok's browser warning interstitial page in dev
    'ngrok-skip-browser-warning': 'true',
  },
})

// ── Response interceptor — silent token refresh on 401 ─────────────────────
// The refresh endpoint reads the refresh cookie and re-sets new cookies.
// We just need to retry the original request once refresh succeeds.

let isRefreshing = false
let refreshQueue: Array<() => void> = []

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    const isAuthRoute = original?.url?.includes('/auth/otp/') || original?.url?.includes('/auth/token/refresh/')

    if (error.response?.status === 401 && !original._retry && !isAuthRoute) {
      original._retry = true

      if (isRefreshing) {
        return new Promise((resolve) => {
          refreshQueue.push(() => resolve(api(original)))
        })
      }

      isRefreshing = true

      try {
        await axios.post(`${API_BASE}/auth/token/refresh/`, {}, {
          withCredentials: true,
          headers: { 'ngrok-skip-browser-warning': 'true' },
        })
        refreshQueue.forEach((cb) => cb())
        refreshQueue = []
        return api(original)
      } catch {
        refreshQueue = []
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
        return Promise.reject(error)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

// ── Error helper ─────────────────────────────────────────────────────────────

export function apiErrorMessage(err: unknown, fallback = 'Hitilafu imetokea. Jaribu tena.'): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as Record<string, unknown> | undefined
    if (data && typeof data.detail === 'string') return data.detail
    if (data) {
      const firstKey = Object.keys(data)[0]
      const val = data[firstKey]
      if (Array.isArray(val) && typeof val[0] === 'string') return val[0]
      if (typeof val === 'string') return val
    }
  }
  return fallback
}