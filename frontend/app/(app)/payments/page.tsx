'use client'

/**
 * BizYangu — Payments (Reconciliation) page.
 * Owner-only: lists all M-Pesa money received, shows matched vs unmatched,
 * and allows manual linking of unmatched payments to existing transactions.
 */

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useAuthStore } from '@/lib/auth'
import { listMpesaTransactions, reconcileMpesaTransaction } from '@/lib/payments'
import { listTransactions } from '@/lib/transactions'
import type { MPesaTransaction, Transaction } from '@/lib/types'
import { COPY } from '@/lib/copy'

// ── Filter tabs ───────────────────────────────────────────────────────────────

type FilterTab = 'all' | 'unmatched' | 'matched'

// ── Reconcile modal ───────────────────────────────────────────────────────────

function ReconcileModal({
  mpesaTxn,
  onClose,
  onDone,
}: {
  mpesaTxn: MPesaTransaction
  onClose: () => void
  onDone: () => void
}) {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedTxnId, setSelectedTxnId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    listTransactions({ payment: 'MPESA', type: 'SALE' })
      .then((res) => setTransactions(res.results.filter((t) => t.payment_status === 'PENDING' && !t.is_voided)))
      .catch(() => setError(COPY.PAYMENTS_LOAD_ERROR))
      .finally(() => setLoading(false))
  }, [])

  async function handleLink() {
    if (!selectedTxnId) return
    setSaving(true)
    setError('')
    try {
      await reconcileMpesaTransaction(mpesaTxn.id, selectedTxnId)
      onDone()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || COPY.PAYMENTS_SYNC_ERROR)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 50,
      background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 'var(--sp-4)',
    }}>
      <div className="card" style={{ maxWidth: 460, width: '100%', maxHeight: '80dvh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-4)' }}>
          <h2 style={{ fontSize: 'var(--fs-md)', fontWeight: 700 }}>{COPY.PAYMENTS_LINK_MODAL_TITLE}</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-muted)', fontSize: 20 }}>✕</button>
        </div>

        {/* M-Pesa txn summary */}
        <div style={{
          background: 'var(--surface-2)', borderRadius: 'var(--radius-default)',
          padding: 'var(--sp-3)', marginBottom: 'var(--sp-4)', fontSize: 'var(--fs-sm)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--sp-1)' }}>
            <span style={{ color: 'var(--color-muted)' }}>{COPY.PAYMENTS_MPESA_RECEIPT}</span>
            <span className="mono" style={{ color: 'var(--color-teal)' }}>{mpesaTxn.mpesa_receipt_number}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--sp-1)' }}>
            <span style={{ color: 'var(--color-muted)' }}>{COPY.PAYMENTS_AMOUNT}</span>
            <span style={{ fontWeight: 700 }}>KES {Number(mpesaTxn.amount).toLocaleString()}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--color-muted)' }}>{COPY.PAYMENTS_PHONE}</span>
            <span className="mono">{mpesaTxn.phone_number}</span>
          </div>
        </div>

        <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-3)' }}>
          {COPY.PAYMENTS_SELECT_SALE}
        </p>

        {/* Pending M-Pesa transactions list */}
        <div style={{ flex: 1, overflowY: 'auto', marginBottom: 'var(--sp-4)' }}>
          {loading ? (
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)', textAlign: 'center', padding: 'var(--sp-5)' }}>
              {COPY.LOADING}
            </p>
          ) : transactions.length === 0 ? (
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)', textAlign: 'center', padding: 'var(--sp-5)' }}>
              {COPY.PAYMENTS_NO_PENDING}
            </p>
          ) : (
            transactions.map((txn) => (
              <button
                key={txn.id}
                onClick={() => setSelectedTxnId(txn.id)}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  width: '100%', padding: 'var(--sp-3)',
                  marginBottom: 'var(--sp-2)',
                  border: `1px solid ${selectedTxnId === txn.id ? 'var(--color-teal)' : 'var(--surface-4)'}`,
                  background: selectedTxnId === txn.id ? 'rgba(0,229,196,0.08)' : 'var(--surface-2)',
                  borderRadius: 'var(--radius-default)',
                  cursor: 'pointer', textAlign: 'left',
                  transition: 'all 0.15s',
                }}
              >
                <div>
                  <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-teal)', display: 'block' }}>
                    {txn.reference_number}
                  </span>
                  <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                    {new Date(txn.created_at).toLocaleString('en-KE', { dateStyle: 'short', timeStyle: 'short' })}
                  </span>
                </div>
                <span style={{ fontWeight: 700, color: 'var(--color-teal)', fontSize: 'var(--fs-sm)' }}>
                  KES {Number(txn.total_amount).toLocaleString()}
                </span>
              </button>
            ))
          )}
        </div>

        {error && (
          <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-xs)', marginBottom: 'var(--sp-3)' }}>{error}</p>
        )}

        <div style={{ display: 'flex', gap: 'var(--sp-3)' }}>
          <button className="btn-ghost" onClick={onClose} style={{ flex: 1 }}>{COPY.CANCEL}</button>
          <button
            className="btn-primary"
            onClick={handleLink}
            disabled={!selectedTxnId || saving}
            style={{ flex: 1 }}
          >
            {saving ? COPY.PAYMENTS_LINKING : COPY.PAYMENTS_LINK_CONFIRM}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PaymentsPage() {
  const user = useAuthStore((s) => s.user)

  const [mpesaTxns, setMpesaTxns] = useState<MPesaTransaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<FilterTab>('all')
  const [reconcileTarget, setReconcileTarget] = useState<MPesaTransaction | null>(null)

  // Only owners/managers should see this page; guard at layout level,
  // but also show a soft message here.
  const isOwnerOrManager = user?.role === 'OWNER' || user?.role === 'MANAGER'

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    listMpesaTransactions()
      .then((res) => setMpesaTxns(res.results))
      .catch(() => setError(COPY.PAYMENTS_HISTORY_ERROR))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (isOwnerOrManager) load()
  }, [isOwnerOrManager, load])

  if (!isOwnerOrManager) {
    return (
      <main style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--color-muted)' }}>{COPY.PAYMENTS_OWNER_ONLY}</p>
      </main>
    )
  }

  const filtered = mpesaTxns.filter((t) => {
    if (tab === 'unmatched') return !t.is_matched
    if (tab === 'matched') return t.is_matched
    return true
  })

  const unmatchedCount = mpesaTxns.filter((t) => !t.is_matched).length

  return (
    <main data-main style={{ padding: 'var(--sp-5) var(--sp-4)' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--sp-5)' }}>
        <div>
          <h1 style={{ fontSize: 'var(--fs-lg)', fontWeight: 700, marginBottom: 4 }}>{COPY.PAYMENTS_TITLE}</h1>
          <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
            {COPY.PAYMENTS_SUBTITLE}
          </p>
        </div>
        <button className="btn-ghost" onClick={load} style={{ fontSize: 'var(--fs-xs)' }}>
          {COPY.PAYMENTS_REFRESH}
        </button>
      </div>

      {/* Unmatched banner */}
      {unmatchedCount > 0 && (
        <div style={{
          background: 'rgba(251,191,36,0.1)', border: '1px solid var(--color-amber)',
          borderRadius: 'var(--radius-card)', padding: 'var(--sp-3) var(--sp-4)',
          marginBottom: 'var(--sp-4)', fontSize: 'var(--fs-sm)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ color: 'var(--color-amber)' }}>
            {COPY.PAYMENTS_UNMATCHED_BANNER.replace('{count}', String(unmatchedCount))}
          </span>
          <button
            className="btn-ghost"
            style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-amber)' }}
            onClick={() => setTab('unmatched')}
          >
            {COPY.PAYMENTS_VIEW}
          </button>
        </div>
      )}

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
        {(['all', 'unmatched', 'matched'] as FilterTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: 'var(--sp-1) var(--sp-3)',
              borderRadius: 'var(--radius-default)',
              border: `1px solid ${tab === t ? 'var(--color-teal)' : 'var(--surface-4)'}`,
              background: tab === t ? 'rgba(0,229,196,0.1)' : 'var(--surface-2)',
              color: tab === t ? 'var(--color-teal)' : 'var(--color-muted)',
              cursor: 'pointer',
              fontSize: 'var(--fs-xs)',
              fontFamily: 'var(--font-display)',
            }}
          >
            {t === 'all' ? COPY.PAYMENTS_TAB_ALL : t === 'unmatched' ? COPY.PAYMENTS_TAB_UNMATCHED.replace('{count}', String(unmatchedCount)) : COPY.PAYMENTS_TAB_MATCHED}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 'var(--sp-8)', color: 'var(--color-muted)' }}>
          {COPY.LOADING}
        </div>
      ) : error ? (
        <div style={{ textAlign: 'center', padding: 'var(--sp-8)', color: 'var(--color-error)' }}>
          {error}
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 'var(--sp-8)', color: 'var(--color-muted)', fontSize: 'var(--fs-sm)' }}>
          {tab === 'unmatched' ? COPY.PAYMENTS_EMPTY_UNMATCHED : COPY.PAYMENTS_EMPTY_ALL}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
          {filtered.map((txn) => (
            <div
              key={txn.id}
              className="card"
              style={{
                display: 'flex', alignItems: 'center', gap: 'var(--sp-4)',
                padding: 'var(--sp-3) var(--sp-4)',
                borderColor: txn.is_matched ? 'var(--surface-3)' : 'var(--color-amber)',
              }}
            >
              {/* Status dot */}
              <div style={{
                width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                background: txn.is_matched ? 'var(--color-teal)' : 'var(--color-amber)',
              }} />

              {/* Main info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', flexWrap: 'wrap' }}>
                  <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-teal)' }}>
                    {txn.mpesa_receipt_number}
                  </span>
                  {txn.transaction_reference && (
                    <span className="badge badge-muted" style={{ fontSize: 'var(--fs-xs)' }}>
                      → {txn.transaction_reference}
                    </span>
                  )}
                  {!txn.is_matched && (
                    <span className="badge" style={{ fontSize: 'var(--fs-xs)', background: 'rgba(251,191,36,0.15)', color: 'var(--color-amber)', border: '1px solid var(--color-amber)' }}>
                      {COPY.PAYMENTS_UNMATCHED_BADGE}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 'var(--sp-3)', marginTop: 4, fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                  <span>{txn.phone_number}</span>
                  <span>·</span>
                  <span>{new Date(txn.transaction_date).toLocaleString('en-KE', { dateStyle: 'short', timeStyle: 'short' })}</span>
                </div>
              </div>

              {/* Amount */}
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div style={{ fontWeight: 700, color: 'var(--color-teal)', fontSize: 'var(--fs-sm)' }}>
                  KES {Number(txn.amount).toLocaleString()}
                </div>
              </div>

              {/* Link button (unmatched only) */}
              {!txn.is_matched && (
                <button
                  className="btn-ghost"
                  style={{ fontSize: 'var(--fs-xs)', flexShrink: 0 }}
                  onClick={() => setReconcileTarget(txn)}
                >
                  {COPY.PAYMENTS_LINK}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Reconcile modal */}
      {reconcileTarget && (
        <ReconcileModal
          mpesaTxn={reconcileTarget}
          onClose={() => setReconcileTarget(null)}
          onDone={() => {
            setReconcileTarget(null)
            load()
          }}
        />
      )}
    </main>
  )
}
