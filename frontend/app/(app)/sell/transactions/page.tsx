'use client'

/**
 * BizYangu — Transaction history.
 * Lists today's transactions by default. Owner/manager can void.
 * Cashier sees only their own.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useAuthStore } from '@/lib/auth'
import { listTransactions, voidTransaction, refundTransaction, lookupReceipt } from '@/lib/transactions'
import { apiErrorMessage } from '@/lib/api'
import { fetchBusiness } from '@/lib/business'
import { shareReceiptImage } from '@/lib/receipt-share'
import ReceiptCard from '@/components/sell/ReceiptCard'
import type { Transaction, Business } from '@/lib/types'
import { COPY } from '@/lib/copy'

const PAYMENT_LABEL: Record<string, string> = {
  CASH: COPY.TXN_PAYMENT_CASH,
  MPESA: 'M-Pesa',
  MIXED: COPY.TXN_PAYMENT_MIXED,
  CREDIT: COPY.TXN_PAYMENT_CREDIT,
}

const TYPE_LABEL: Record<string, string> = {
  SALE: COPY.TXN_TYPE_SALE,
  STOCK_IN: COPY.TXN_TYPE_STOCK_IN,
  ADJUSTMENT: COPY.TXN_TYPE_ADJUSTMENT,
  LOSS: COPY.TXN_TYPE_LOSS,
  DAMAGE: COPY.TXN_TYPE_DAMAGE,
  REFUND: COPY.TXN_TYPE_REFUND,
  TRANSFER: COPY.TXN_TYPE_TRANSFER,
}

function formatDatetime(iso: string): string {
  return new Date(iso).toLocaleString('en-KE', { dateStyle: 'short', timeStyle: 'short' })
}

function TransactionRow({
  txn,
  canVoid,
  onVoid,
  onRefund,
  onViewReceipt,
}: {
  txn: Transaction
  canVoid: boolean
  onVoid: (txn: Transaction) => void
  onRefund: (txn: Transaction) => void
  onViewReceipt: (txn: Transaction) => void
}) {
  const refundedAmount = Number(txn.refunded_amount || 0)
  const isFullyRefunded = refundedAmount > 0 && refundedAmount >= Number(txn.total_amount)
  const isPartiallyRefunded = refundedAmount > 0 && !isFullyRefunded

  return (
    <div style={{
      background: 'var(--surface-2)',
      borderRadius: 'var(--radius-card)',
      padding: 'var(--sp-4)',
      marginBottom: 'var(--sp-3)',
      border: txn.is_voided ? '1px solid var(--surface-3)' : '1px solid var(--surface-3)',
      opacity: txn.is_voided ? 0.5 : 1,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--sp-2)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-1)', flexWrap: 'wrap' }}>
            <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-teal)' }}>
              {txn.reference_number}
            </span>
            <span className={`badge ${txn.is_voided ? 'badge-error' : 'badge-muted'}`} style={{ fontSize: 'var(--fs-xs)' }}>
              {txn.is_voided ? COPY.TXN_VOIDED_BADGE : TYPE_LABEL[txn.type] || txn.type}
            </span>
            {!txn.is_voided && isFullyRefunded && (
              <span className="badge badge-error" style={{ fontSize: 'var(--fs-xs)' }}>{COPY.TXN_REFUNDED_BADGE}</span>
            )}
            {!txn.is_voided && isPartiallyRefunded && (
              <span className="badge" style={{ fontSize: 'var(--fs-xs)', background: 'rgba(251,191,36,0.15)', color: 'var(--color-amber)', border: '1px solid var(--color-amber)' }}>
                {COPY.TXN_PARTIALLY_REFUNDED_BADGE}
              </span>
            )}
          </div>
          <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
            {formatDatetime(txn.created_at)} · {txn.created_by_name} · {PAYMENT_LABEL[txn.payment_method] || txn.payment_method}
            {txn.mpesa_reference ? ` · ${txn.mpesa_reference}` : ''}
          </div>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 'var(--fs-md)', color: txn.is_voided ? 'var(--color-muted)' : 'var(--color-off-white)' }}>
            KES {Number(txn.total_amount).toLocaleString()}
          </div>
          {isPartiallyRefunded && (
            <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-amber)' }}>
              -KES {refundedAmount.toLocaleString()}
            </div>
          )}
          <div style={{ display: 'flex', gap: 'var(--sp-3)', justifyContent: 'flex-end', marginTop: 4 }}>
            {txn.type === 'SALE' && (
              <button
                onClick={() => onViewReceipt(txn)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--color-teal)', fontSize: 'var(--fs-xs)',
                }}
              >
                {COPY.TXN_RECEIPT_BTN}
              </button>
            )}
            {canVoid && txn.type === 'SALE' && !txn.is_voided && !isFullyRefunded && (
              <button
                onClick={() => onRefund(txn)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--color-amber)', fontSize: 'var(--fs-xs)',
                }}
              >
                {COPY.TXN_REFUND_BTN}
              </button>
            )}
            {canVoid && !txn.is_voided && (
              <button
                onClick={() => onVoid(txn)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--color-error)', fontSize: 'var(--fs-xs)',
                }}
              >
                {COPY.TXN_VOID_BTN}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Line items (collapsed summary) */}
      {txn.items.length > 0 && (
        <div style={{ marginTop: 'var(--sp-2)', paddingTop: 'var(--sp-2)', borderTop: '1px solid var(--surface-3)' }}>
          {txn.items.map((item) => (
            <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
              <span>{item.product_name} × {Number(item.quantity)}</span>
              <span>KES {Number(item.subtotal).toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}

      {txn.is_voided && txn.void_reason && (
        <div style={{ marginTop: 'var(--sp-2)', fontSize: 'var(--fs-xs)', color: 'var(--color-error)' }}>
          {COPY.TXN_VOID_REASON_LABEL} {txn.void_reason}
        </div>
      )}
    </div>
  )
}

// ── Void modal ────────────────────────────────────────────────────────────────

function VoidModal({
  txn,
  onCancel,
  onConfirm,
}: {
  txn: Transaction
  onCancel: () => void
  onConfirm: (reason: string) => Promise<void>
}) {
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit() {
    if (!reason.trim()) { setError(COPY.TXN_REASON_REQUIRED); return }
    setLoading(true)
    setError('')
    try {
      await onConfirm(reason.trim())
    } catch {
      setError(COPY.SELL_GENERIC_ERROR)
      setLoading(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 100, padding: 'var(--sp-5)',
    }}>
      <div className="card" style={{ maxWidth: 400, width: '100%' }}>
        <h3 style={{ marginBottom: 'var(--sp-3)' }}>{COPY.TXN_VOID_TITLE}</h3>
        <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-4)' }}>
          {COPY.TXN_VOID_CONFIRM_PREFIX}{' '}
          <span className="mono" style={{ color: 'var(--color-teal)' }}>{txn.reference_number}</span>{' '}
          (KES {Number(txn.total_amount).toLocaleString()}). {COPY.TXN_STOCK_RESTORED}
        </p>
        <div style={{ marginBottom: 'var(--sp-3)' }}>
          <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
            {COPY.TXN_VOID_REASON_FIELD}
          </label>
          <textarea
            className="input"
            rows={3}
            placeholder={COPY.TXN_VOID_REASON_PLACEHOLDER}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            style={{ width: '100%', resize: 'vertical' }}
          />
        </div>
        {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-xs)', marginBottom: 'var(--sp-3)' }}>{error}</p>}
        <div style={{ display: 'flex', gap: 'var(--sp-3)' }}>
          <button className="btn-ghost" onClick={onCancel} style={{ flex: 1 }} disabled={loading}>
            {COPY.CANCEL}
          </button>
          <button className="btn-destructive" onClick={handleSubmit} style={{ flex: 1 }} disabled={loading}>
            {loading ? COPY.TXN_VOIDING : COPY.TXN_VOID_CONFIRM_BTN}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Refund modal ──────────────────────────────────────────────────────────────
// Amount-only by design: the owner/manager just types the KES amount being
// handed back to the customer. No items, no quantities, no percentages —
// the backend figures out stock restoration internally. Pre-filled with the
// full remaining refundable amount so a full refund is a one-tap confirm.

function RefundModal({
  txn,
  onCancel,
  onConfirm,
}: {
  txn: Transaction
  onCancel: () => void
  onConfirm: (amount: string, reason: string) => Promise<void>
}) {
  const remaining = Number(txn.total_amount) - Number(txn.refunded_amount || 0)
  const [amount, setAmount] = useState(remaining > 0 ? String(remaining) : '')
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit() {
    const amountNum = Number(amount)
    if (!amount || amountNum <= 0) {
      setError(COPY.TXN_REFUND_AMOUNT_REQUIRED)
      return
    }
    if (!reason.trim()) {
      setError(COPY.TXN_REASON_REQUIRED)
      return
    }
    setLoading(true)
    setError('')
    try {
      await onConfirm(amountNum.toFixed(2), reason.trim())
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || COPY.SELL_GENERIC_ERROR)
      setLoading(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 100, padding: 'var(--sp-5)',
    }}>
      <div className="card" style={{ maxWidth: 400, width: '100%' }}>
        <h3 style={{ marginBottom: 'var(--sp-3)' }}>{COPY.TXN_REFUND_TITLE}</h3>
        <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-4)' }}>
          {COPY.TXN_REFUND_CONFIRM_PREFIX}{' '}
          <span className="mono" style={{ color: 'var(--color-teal)' }}>{txn.reference_number}</span>.{' '}
          {COPY.TXN_REFUND_REMAINING_LABEL} KES {remaining.toLocaleString()}.
        </p>

        <div style={{ marginBottom: 'var(--sp-3)' }}>
          <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
            {COPY.TXN_REFUND_AMOUNT_FIELD}
          </label>
          <input
            className="input"
            type="number"
            min={0}
            max={remaining}
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            style={{ width: '100%', fontSize: 'var(--fs-lg)', fontWeight: 700 }}
          />
        </div>

        <div style={{ marginBottom: 'var(--sp-3)' }}>
          <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
            {COPY.TXN_REFUND_REASON_FIELD}
          </label>
          <textarea
            className="input"
            rows={2}
            placeholder={COPY.TXN_REFUND_REASON_PLACEHOLDER}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            style={{ width: '100%', resize: 'vertical' }}
          />
        </div>

        {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-xs)', marginBottom: 'var(--sp-3)' }}>{error}</p>}

        <div style={{ display: 'flex', gap: 'var(--sp-3)' }}>
          <button className="btn-ghost" onClick={onCancel} style={{ flex: 1 }} disabled={loading}>
            {COPY.CANCEL}
          </button>
          <button
            className="btn-primary"
            onClick={handleSubmit}
            style={{ flex: 1, background: 'var(--color-amber)', borderColor: 'var(--color-amber)' }}
            disabled={loading}
          >
            {loading ? COPY.TXN_REFUNDING : COPY.TXN_REFUND_CONFIRM_BTN}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Receipt modal ─────────────────────────────────────────────────────────────
// Re-shows a past sale's ReceiptCard (same component the success screen uses)
// with the same image-based "as-is, dark or light" WhatsApp share.

function ReceiptModal({
  txn,
  business,
  businessName,
  onClose,
}: {
  txn: Transaction
  business: Business | null
  businessName: string
  onClose: () => void
}) {
  const receiptRef = useRef<HTMLDivElement>(null)
  const [sharing, setSharing] = useState(false)
  const [shareError, setShareError] = useState('')

  async function handleShare() {
    if (!receiptRef.current || sharing) return
    setSharing(true)
    setShareError('')
    try {
      await shareReceiptImage(receiptRef.current, txn, businessName)
    } catch {
      setShareError(COPY.TXN_RECEIPT_SHARE_FAIL)
    } finally {
      setSharing(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 100, padding: 'var(--sp-5)', overflowY: 'auto',
    }}>
      <div style={{ maxWidth: 420, width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--sp-3)' }}>
          <button className="btn-ghost" onClick={onClose} style={{ fontSize: 'var(--fs-xs)' }}>
            {COPY.TXN_CLOSE}
          </button>
        </div>

        <div style={{ marginBottom: 'var(--sp-5)' }} ref={receiptRef}>
          <ReceiptCard transaction={txn} business={business} businessNameFallback={businessName} />
        </div>

        <button
          className="btn-secondary"
          onClick={handleShare}
          disabled={sharing}
          style={{ width: '100%' }}
        >
          {sharing ? COPY.SELL_SHARE_SENDING : COPY.SELL_SHARE_RECEIPT_BTN}
        </button>

        {shareError && (
          <div style={{ textAlign: 'center', fontSize: 'var(--fs-xs)', color: 'var(--color-error)', marginTop: 'var(--sp-2)' }}>
            {shareError}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Receipt lookup (item D12 — search-by-serial) ────────────────────────────
// Pilot-scoped fallback per the pre-pilot doc: no camera/QR-scanner plugin
// exists in the app yet, so this is a plain text box against the same
// receipt_lookup endpoint a future scanner would call. Swapping in camera
// input later just needs to call onFound with the decoded string instead
// of the input value — this component's shape doesn't need to change.

function ReceiptLookupBox({ onFound }: { onFound: (txn: Transaction) => void }) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleLookup() {
    const trimmed = value.trim()
    if (!trimmed) { setError(COPY.TXN_LOOKUP_EMPTY_INPUT); return }
    setLoading(true)
    setError('')
    try {
      const txn = await lookupReceipt(trimmed)
      onFound(txn)
      setValue('')
      setOpen(false)
    } catch (err: unknown) {
      // Backend already returns the exact "no receipt found" copy as
      // `detail` on a 404 (see MESSAGES.RECEIPT_NOT_FOUND) — apiErrorMessage
      // surfaces that directly, same pattern as creditors/payments pages.
      setError(apiErrorMessage(err, COPY.TXN_LOOKUP_ERROR))
    } finally {
      setLoading(false)
    }
  }

  if (!open) {
    return (
      <button
        className="btn-ghost"
        onClick={() => setOpen(true)}
        style={{ fontSize: 'var(--fs-xs)', marginBottom: 'var(--sp-4)' }}
      >
        {COPY.TXN_LOOKUP_TOGGLE}
      </button>
    )
  }

  return (
    <div style={{ marginBottom: 'var(--sp-5)' }}>
      <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
        <input
          className="input"
          placeholder={COPY.TXN_LOOKUP_PLACEHOLDER}
          value={value}
          onChange={(e) => { setValue(e.target.value); setError('') }}
          onKeyDown={(e) => { if (e.key === 'Enter') handleLookup() }}
          autoFocus
          style={{ flex: 1 }}
        />
        <button className="btn-primary" onClick={handleLookup} disabled={loading} style={{ fontSize: 'var(--fs-xs)', whiteSpace: 'nowrap' }}>
          {loading ? COPY.TXN_LOOKUP_SEARCHING : COPY.TXN_LOOKUP_BTN}
        </button>
        <button className="btn-ghost" onClick={() => { setOpen(false); setError(''); setValue('') }} style={{ fontSize: 'var(--fs-xs)' }}>
          {COPY.TXN_CLOSE}
        </button>
      </div>
      {error && (
        <div style={{ color: 'var(--color-error)', fontSize: 'var(--fs-xs)', marginTop: 'var(--sp-2)' }}>
          {error}
        </div>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TransactionsPage() {
  const user = useAuthStore((s) => s.user)
  const canVoid = user?.role === 'OWNER' || user?.role === 'MANAGER'

  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dateFilter, setDateFilter] = useState(new Date().toISOString().slice(0, 10))
  const [typeFilter, setTypeFilter] = useState('')
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)

  const [voidTarget, setVoidTarget] = useState<Transaction | null>(null)
  const [refundTarget, setRefundTarget] = useState<Transaction | null>(null)
  const [receiptTarget, setReceiptTarget] = useState<Transaction | null>(null)
  const [business, setBusiness] = useState<Business | null>(null)

  useEffect(() => {
    fetchBusiness().then(setBusiness).catch(() => {})
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await listTransactions({
        date: dateFilter || undefined,
        type: typeFilter || undefined,
        page,
      })
      setTransactions(result.results)
      setTotalCount(result.count)
    } catch {
      setError(COPY.TXN_LOAD_ERROR)
    } finally {
      setLoading(false)
    }
  }, [dateFilter, typeFilter, page])

  useEffect(() => { load() }, [load])

  async function handleVoidConfirm(reason: string) {
    if (!voidTarget) return
    await voidTransaction(voidTarget.id, reason)
    setVoidTarget(null)
    load()
  }

  async function handleRefundConfirm(amount: string, reason: string) {
    if (!refundTarget) return
    await refundTransaction({ transaction_id: refundTarget.id, amount, reason })
    setRefundTarget(null)
    load()
  }

  const totalSales = transactions
    .filter((t) => t.type === 'SALE' && !t.is_voided)
    .reduce((sum, t) => sum + Number(t.total_amount), 0)

  const pageSize = 50

  return (
    <div data-main style={{ minHeight: '100dvh', background: 'var(--surface-0)' }}>

      {/* Header */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: 'var(--sp-3) var(--sp-4)',
        borderBottom: '1px solid var(--surface-2)',
        background: 'var(--surface-1)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
          <Link href="/sell" className="btn-ghost" style={{ padding: 'var(--sp-1) var(--sp-2)', fontSize: 'var(--fs-xs)' }}>{COPY.TXN_BACK}</Link>
          <span style={{ fontWeight: 700 }}>{COPY.TXN_TITLE}</span>
        </div>
        <Link href="/sell" className="btn-primary" style={{ fontSize: 'var(--fs-xs)' }}>
          {COPY.TXN_NEW_SALE}
        </Link>
      </header>

      <main style={{ maxWidth: 720, margin: '0 auto', padding: 'var(--sp-5) var(--sp-4)' }}>

        {/* Receipt lookup — item D12 */}
        <ReceiptLookupBox onFound={setReceiptTarget} />

        {/* Filters */}
        <div style={{ display: 'flex', gap: 'var(--sp-3)', marginBottom: 'var(--sp-5)', flexWrap: 'wrap' }}>
          <input
            className="input"
            type="date"
            value={dateFilter}
            onChange={(e) => { setDateFilter(e.target.value); setPage(1) }}
            style={{ flex: 1, minWidth: 160 }}
          />
          <select
            className="input"
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1) }}
            style={{ flex: 1, minWidth: 140 }}
          >
            <option value="">{COPY.TXN_TYPE_ALL}</option>
            <option value="SALE">{COPY.TXN_TYPE_SALE}</option>
            <option value="STOCK_IN">{COPY.TXN_TYPE_STOCK_IN}</option>
            <option value="ADJUSTMENT">{COPY.TXN_TYPE_ADJUSTMENT}</option>
            <option value="LOSS">{COPY.TXN_TYPE_LOSS}</option>
          </select>
          <button className="btn-ghost" onClick={() => { setDateFilter(''); setPage(1) }}
            style={{ fontSize: 'var(--fs-xs)' }}>
            {COPY.TXN_SHOW_ALL}
          </button>
        </div>

        {/* Summary banner */}
        {!loading && transactions.length > 0 && (
          <div className="card-stat" style={{ marginBottom: 'var(--sp-5)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.TXN_TOTAL_SALES_LABEL}</div>
              <div style={{ fontSize: 'var(--fs-lg)', fontWeight: 700, color: 'var(--color-teal)' }}>
                KES {totalSales.toLocaleString()}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.TXN_COUNT_LABEL}</div>
              <div style={{ fontSize: 'var(--fs-lg)', fontWeight: 700 }}>{totalCount}</div>
            </div>
          </div>
        )}

        {/* List */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: 'var(--sp-7)', color: 'var(--color-muted)' }}>{COPY.LOADING}</div>
        ) : error ? (
          <div style={{ color: 'var(--color-error)', textAlign: 'center', padding: 'var(--sp-5)' }}>{error}</div>
        ) : transactions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 'var(--sp-7)', color: 'var(--color-muted)' }}>
            {dateFilter ? COPY.TXN_EMPTY_DATE.replace('{date}', dateFilter) : COPY.TXN_EMPTY_ALL}
          </div>
        ) : (
          transactions.map((txn) => (
            <TransactionRow
              key={txn.id}
              txn={txn}
              canVoid={canVoid}
              onVoid={setVoidTarget}
              onRefund={setRefundTarget}
              onViewReceipt={setReceiptTarget}
            />
          ))
        )}

        {/* Pagination */}
        {totalCount > pageSize && (
          <div style={{ display: 'flex', justifyContent: 'center', gap: 'var(--sp-3)', marginTop: 'var(--sp-5)' }}>
            <button className="btn-ghost" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
              {COPY.TXN_PAGE_PREV}
            </button>
            <span className="mono" style={{ color: 'var(--color-muted)', alignSelf: 'center', fontSize: 'var(--fs-xs)' }}>
              {COPY.TXN_PAGE_LABEL.replace('{page}', String(page)).replace('{total}', String(Math.ceil(totalCount / pageSize)))}
            </span>
            <button className="btn-ghost" onClick={() => setPage((p) => p + 1)} disabled={page * pageSize >= totalCount}>
              {COPY.TXN_PAGE_NEXT}
            </button>
          </div>
        )}
      </main>

      {/* Void modal */}
      {voidTarget && (
        <VoidModal
          txn={voidTarget}
          onCancel={() => setVoidTarget(null)}
          onConfirm={handleVoidConfirm}
        />
      )}

      {/* Refund modal */}
      {refundTarget && (
        <RefundModal
          txn={refundTarget}
          onCancel={() => setRefundTarget(null)}
          onConfirm={handleRefundConfirm}
        />
      )}

      {/* Receipt modal */}
      {receiptTarget && (
        <ReceiptModal
          txn={receiptTarget}
          business={business}
          businessName={business?.name || 'BizYangu'}
          onClose={() => setReceiptTarget(null)}
        />
      )}
    </div>
  )
}
