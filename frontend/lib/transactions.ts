/**
 * BizYangu — transactions API calls (SELL MODE).
 */

import { api } from './api'
import type { PaymentMethod, Transaction } from './types'

export interface SaleLineItemPayload {
  product_id: string
  quantity: string
}

export interface SaleCreatePayload {
  items: SaleLineItemPayload[]
  payment_method: PaymentMethod
  mpesa_reference?: string
  notes?: string
}

export async function createSale(payload: SaleCreatePayload): Promise<Transaction> {
  const { data } = await api.post('/transactions/sale/', payload)
  return data
}

export interface TransactionListParams {
  type?: string
  payment?: string
  date?: string
  page?: number
}

export interface TransactionListResult {
  count: number
  page: number
  page_size: number
  results: Transaction[]
}

export async function listTransactions(params: TransactionListParams = {}): Promise<TransactionListResult> {
  const { data } = await api.get('/transactions/', { params })
  return data
}

export async function fetchTransaction(id: string): Promise<Transaction> {
  const { data } = await api.get(`/transactions/${id}/`)
  return data
}

export async function voidTransaction(id: string, reason: string): Promise<{ detail: string; transaction: Transaction }> {
  const { data } = await api.post(`/transactions/${id}/void/`, { reason })
  return data
}

export interface RefundCreatePayload {
  transaction_id: string
  amount: string
  reason: string
}

/**
 * Refunds a plain KES amount from a completed sale. The cashier/owner just
 * types the amount handed back to the customer — no items, no quantities.
 * The backend apportions stock restoration internally; the caller never
 * needs to know or show that math.
 */
export async function refundTransaction(payload: RefundCreatePayload): Promise<{ detail: string; transaction: Transaction }> {
  const { data } = await api.post('/transactions/refund/', payload)
  return data
}