/**
 * BizYangu — transactions API calls (SELL MODE).
 */

import { api } from './api'
import type { PaymentMethod, Transaction, Product } from './types'

export interface SaleLineItemPayload {
  // Catalog item: product_id only. Freeform item (Phase 9, sell-without-
  // inventory): name + unit_price instead, no product_id. Mutually
  // exclusive — the backend rejects both or neither being present.
  product_id?: string
  name?: string
  unit_price?: string
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

// ── Reconciliation queue (Phase 9.2, minimal) ─────────────────────────────────
// Closes the loop on the freeform/"custom" items above: once a cashier
// rings up something not in the catalog, it sits here until an
// owner/manager links it to a real product on the Stock page.

export interface UnreconciledGroup {
  name: string
  item_count: number
  total_quantity: string
  total_value: string
  first_sold_at: string
  last_sold_at: string
}

export async function listUnreconciled(): Promise<UnreconciledGroup[]> {
  const { data } = await api.get('/transactions/unreconciled/')
  return data
}

export interface ResolveUnreconciledPayload {
  name: string
  // Exactly one of these — pick an existing product, or create a new one.
  product_id?: string
  new_product?: {
    name?: string
    selling_price: string
    cost_price?: string
    unit?: string
    current_stock?: string
    low_stock_threshold?: string
  }
}

export async function resolveUnreconciled(
  payload: ResolveUnreconciledPayload
): Promise<{ product: Product; resolved_count: number }> {
  const { data } = await api.post('/transactions/unreconciled/resolve/', payload)
  return data
}