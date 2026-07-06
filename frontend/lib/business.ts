/**
 * BizYangu — business setup API calls.
 */

import { api } from './api'
import type { Business, BusinessType, StaffMember, UserRole } from './types'

export interface BusinessSetupPayload {
  name: string
  type: BusinessType
  custom_type_name?: string
  mpesa_till_number?: string
  mpesa_paybill_number?: string
  mpesa_business_shortcode?: string
}

export async function setupBusiness(payload: BusinessSetupPayload): Promise<Business> {
  const { data } = await api.post('/business/setup/', payload)
  return data
}

export async function fetchBusiness(): Promise<Business> {
  const { data } = await api.get('/business/')
  return data
}

export type BusinessUpdatePayload = Partial<{
  name: string
  type: BusinessType
  custom_type_name: string
  mpesa_till_number: string
  mpesa_paybill_number: string
  mpesa_business_shortcode: string
  address: string
  currency: string
  timezone: string
}>

export async function updateBusiness(payload: BusinessUpdatePayload): Promise<Business> {
  const { data } = await api.patch('/business/', payload)
  return data
}

// ── Staff management ────────────────────────────────────────────────────────

export async function fetchStaff(): Promise<StaffMember[]> {
  const { data } = await api.get('/business/users/')
  return data
}

export async function removeStaff(userId: string): Promise<void> {
  await api.delete(`/business/users/${userId}/`)
}

export interface InviteStaffResponse {
  invite_url: string
  expires_at: string
  role: UserRole
}

export async function inviteStaff(role: 'CASHIER' | 'MANAGER'): Promise<InviteStaffResponse> {
  const { data } = await api.post('/auth/invite/', { role })
  return data
}

export async function acceptInvite(token: string): Promise<void> {
  await api.post('/auth/join/', { token })
}
