/**
 * BizYangu — customer ledger API calls (Phase 12, creditor UI).
 */

import { api } from './api'
import type { Customer, CustomerDetail, CustomerPayment } from './types'

export interface CustomerListParams {
  owing?: boolean
  sort?: 'amount' | 'age' | 'name'
}

export async function listCustomers(params: CustomerListParams = {}): Promise<Customer[]> {
  const { data } = await api.get('/customers/', {
    params: { owing: params.owing ? 'true' : undefined, sort: params.sort },
  })
  return data
}

export interface CustomerCreatePayload {
  name: string
  phone?: string
  notes?: string
}

export async function createCustomer(payload: CustomerCreatePayload): Promise<Customer> {
  const { data } = await api.post('/customers/', payload)
  return data
}

export async function fetchCustomer(id: string): Promise<CustomerDetail> {
  const { data } = await api.get(`/customers/${id}/`)
  return data
}

export interface SettlementResult {
  detail: string
  payment: CustomerPayment
  remaining_balance: string
}

/**
 * Records a payment against a customer's outstanding balance. Amount-only,
 * same UX shape as `refundTransaction` — one KES figure, nothing about
 * which sale(s) it settles (see backend apps/customers/services.py).
 */
export async function settleCustomerBalance(
  customerId: string,
  amount: string,
  notes?: string
): Promise<SettlementResult> {
  const { data } = await api.post(`/customers/${customerId}/settle/`, { amount, notes })
  return data
}
