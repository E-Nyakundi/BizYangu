/**
 * BizYangu — M-Pesa / payments API client.
 */

import { api } from './api'
import type {
  MPesaSTKRequest, MPesaTransaction, SubscriptionPayment,
  BusinessMpesaCredentials, MpesaTillType, MpesaCredentialsEnv,
} from './types'

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

// ── Subscription billing (BizYangu's own revenue, not a sale) ─────────────────

export interface SubscriptionPaymentPayload {
  phone_number: string
  amount: number
  months?: number
}

/**
 * Initiates an STK push against BizYangu's own (company) shortcode
 * for the business's subscription fee. Separate from initiateStkPush
 * above, which is always about a business receiving payment from
 * THEIR OWN customer.
 */
export async function initiateSubscriptionPayment(
  payload: SubscriptionPaymentPayload,
): Promise<SubscriptionPayment> {
  const { data } = await api.post('/payments/mpesa/subscription/stk-push/', payload)
  return data
}

export async function pollSubscriptionPaymentStatus(
  checkoutRequestId: string,
): Promise<SubscriptionPayment> {
  const { data } = await api.get(`/payments/mpesa/subscription/stk-push/${checkoutRequestId}/status/`)
  return data
}

// ── Business's own M-Pesa credentials (owner-only — their own till) ──────────

export interface BusinessMpesaCredentialsPayload {
  till_type?: MpesaTillType
  shortcode?: string
  consumer_key?: string
  // Omit or leave blank to keep the currently-saved secret unchanged.
  consumer_secret?: string
  passkey?: string
  env?: MpesaCredentialsEnv
}

export async function fetchBusinessMpesaCredentials(): Promise<BusinessMpesaCredentials> {
  const { data } = await api.get('/payments/mpesa/business-credentials/')
  return data
}

export async function saveBusinessMpesaCredentials(
  payload: BusinessMpesaCredentialsPayload,
): Promise<BusinessMpesaCredentials> {
  const { data } = await api.put('/payments/mpesa/business-credentials/', payload)
  return data
}

/**
 * Tests the saved credentials against Daraja for real (fetches an
 * OAuth token, registers C2B URLs for a Paybill) — costs nothing,
 * moves no money. Only on success does the business's own till start
 * being used for their sales.
 */
export async function verifyBusinessMpesaCredentials(): Promise<BusinessMpesaCredentials> {
  const { data } = await api.post('/payments/mpesa/business-credentials/verify/')
  return data
}

/**
 * Falls back to the shared BizYangu shortcode without deleting the
 * saved credentials — e.g. if the business's own till stops working.
 */
export async function deactivateBusinessMpesaCredentials(): Promise<BusinessMpesaCredentials> {
  const { data } = await api.post('/payments/mpesa/business-credentials/deactivate/')
  return data
}
