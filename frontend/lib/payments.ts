/**
 * BizYangu — M-Pesa / payments API client.
 */

import { api } from './api'
import type { MPesaSTKRequest, MPesaTransaction } from './types'

// ── STK Push ──────────────────────────────────────────────────────────────────

export interface StkPushPayload {
  transaction_id: string
  phone_number: string
}

/**
 * Initiates an STK push for an existing PENDING M-Pesa transaction.
 * The sale must already exist (created via POST /transactions/sale/).
 */
export async function initiateStkPush(payload: StkPushPayload): Promise<MPesaSTKRequest> {
  const { data } = await api.post('/payments/mpesa/stk-push/', payload)
  return data
}

/**
 * Poll the status of a pending STK push by checkout_request_id.
 * Call this as a fallback when the WebSocket confirmation does not arrive.
 */
export async function pollStkStatus(checkoutRequestId: string): Promise<MPesaSTKRequest> {
  const { data } = await api.get(`/payments/mpesa/stk-push/${checkoutRequestId}/status/`)
  return data
}

// ── M-Pesa transaction list (reconciliation) ──────────────────────────────────

export interface MPesaTransactionListResult {
  count: number
  results: MPesaTransaction[]
}

export async function listMpesaTransactions(params?: {
  is_matched?: boolean
  page?: number
}): Promise<MPesaTransactionListResult> {
  const { data } = await api.get('/payments/mpesa/transactions/', { params })
  return data
}

// ── Manual reconciliation ─────────────────────────────────────────────────────

export async function reconcileMpesaTransaction(
  mpesaTransactionId: string,
  transactionId: string,
): Promise<{ detail: string }> {
  const { data } = await api.post('/payments/mpesa/reconcile/', {
    mpesa_transaction_id: mpesaTransactionId,
    transaction_id: transactionId,
  })
  return data
}
