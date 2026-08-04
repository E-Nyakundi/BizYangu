'use client'

/**
 * BizYangu — Creditors page (Build Plan v3, Phase 12).
 * Owner/manager only: who owes what, sortable by amount or age, with a
 * per-customer detail view (sale history + settle-a-payment).
 */

import { useState, useEffect, useCallback } from 'react'
import { useAuthStore } from '@/lib/auth'
import {
  listCustomers,
  createCustomer,
  fetchCustomer,
  settleCustomerBalance,
} from '@/lib/customers'
import type { Customer, CustomerDetail } from '@/lib/types'
import { COPY } from '@/lib/copy'

type SortMode = 'amount' | 'age' | 'name'

export default function CreditorsPage() {
  const user = useAuthStore((s) => s.user)
  const isOwnerOrManager = user?.role === 'OWNER' || user?.role === 'MANAGER'

  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [owingOnly, setOwingOnly] = useState(true)
  const [sort, setSort] = useState<SortMode>('amount')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    return listCustomers({ owing: owingOnly, sort })
      .then(setCustomers)
      .catch(() => setError(COPY.CREDITORS_LOAD_ERROR))
      .finally(() => setLoading(false))
  }, [owingOnly, sort])

  useEffect(() => {
    if (isOwnerOrManager) load()
  }, [isOwnerOrManager, load])

  if (!isOwnerOrManager) {
    return (
      <main style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--color-muted)' }}>{COPY.CREDITORS_OWNER_ONLY}</p>
      </main>
    )
  }

  const totalOwed = customers.reduce((sum, c) => sum + Number(c.balance), 0)

  return (
    <main data-main style={{ padding: 'var(--sp-5) var(--sp-4)' }}>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--sp-5)' }}>
        <div>
          <h1 style={{ fontSize: 'var(--fs-lg)', fontWeight: 700, marginBottom: 4 }}>{COPY.CREDITORS_TITLE}</h1>
          <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.CREDITORS_SUBTITLE}</p>
        </div>
        <button className="btn-secondary btn-sm" onClick={() => setShowAdd(true)} style={{ fontSize: 'var(--fs-xs)' }}>
          {COPY.CREDITORS_ADD}
        </button>
      </div>

      {owingOnly && totalOwed > 0 && (
        <div className="card-stat" style={{ marginBottom: 'var(--sp-4)' }}>
          <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.CREDITORS_TOTAL_OWED}</span>
          <div style={{ fontSize: 'var(--fs-xl)', fontWeight: 700, color: 'var(--color-error)' }}>
            KES {totalOwed.toLocaleString()}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)', flexWrap: 'wrap' }}>
        <button
          className={owingOnly ? 'btn-primary' : 'btn-secondary'}
          onClick={() => setOwingOnly((v) => !v)}
          style={{ fontSize: 'var(--fs-xs)' }}
        >
          {owingOnly ? COPY.CREDITORS_FILTER_OWING : COPY.CREDITORS_FILTER_ALL}
        </button>
        <select
          className="input"
          value={sort}
          onChange={(e) => setSort(e.target.value as SortMode)}
          style={{ fontSize: 'var(--fs-xs)', width: 'auto' }}
        >
          <option value="amount">{COPY.CREDITORS_SORT_AMOUNT}</option>
          <option value="age">{COPY.CREDITORS_SORT_AGE}</option>
          <option value="name">{COPY.CREDITORS_SORT_NAME}</option>
        </select>
      </div>

      {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-3)' }}>{error}</p>}

      {loading ? (
        <div style={{ textAlign: 'center', padding: 'var(--sp-7)', color: 'var(--color-muted)' }}>{COPY.CREDITORS_LOADING}</div>
      ) : customers.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 'var(--sp-7)', color: 'var(--color-muted)' }}>
          {owingOnly ? COPY.CREDITORS_EMPTY_OWING : COPY.CREDITORS_EMPTY_ALL}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
          {customers.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedId(c.id)}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                width: '100%', textAlign: 'left',
                background: 'var(--surface-2)', borderRadius: 'var(--radius-card)',
                padding: 'var(--sp-3) var(--sp-4)', border: '1px solid var(--surface-3)',
                cursor: 'pointer',
              }}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: 'var(--fs-sm)' }}>{c.name}</div>
                {c.phone && <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{c.phone}</div>}
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontWeight: 700, color: Number(c.balance) > 0 ? 'var(--color-error)' : 'var(--color-teal)' }}>
                  KES {Number(c.balance).toLocaleString()}
                </div>
                {c.oldest_unpaid_at && (
                  <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                    {COPY.CREDITORS_SINCE.replace('{date}', new Date(c.oldest_unpaid_at).toLocaleDateString())}
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>
      )}

      {selectedId && (
        <CustomerDetailModal
          customerId={selectedId}
          onClose={() => setSelectedId(null)}
          onChanged={load}
        />
      )}

      {showAdd && (
        <AddCustomerModal
          onClose={() => setShowAdd(false)}
          onDone={() => { setShowAdd(false); load() }}
        />
      )}
    </main>
  )
}

function AddCustomerModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit() {
    if (!name.trim()) { setError(COPY.CREDITORS_NAME_ERROR); return }
    setLoading(true)
    setError('')
    try {
      await createCustomer({ name: name.trim(), phone: phone.trim() || undefined })
      onDone()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || COPY.CREDITORS_GENERIC_ERROR)
      setLoading(false)
    }
  }

  return (
    <ModalShell onClose={onClose} title={COPY.CREDITORS_ADD}>
      <input className="input" placeholder={COPY.CREDITORS_NAME_PLACEHOLDER} value={name}
        onChange={(e) => setName(e.target.value)} autoFocus style={{ width: '100%', marginBottom: 'var(--sp-2)' }} />
      <input className="input" placeholder={COPY.CREDITORS_PHONE_PLACEHOLDER} value={phone}
        onChange={(e) => setPhone(e.target.value)} style={{ width: '100%', marginBottom: 'var(--sp-3)' }} />
      {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-xs)', marginBottom: 'var(--sp-3)' }}>{error}</p>}
      <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
        <button className="btn-ghost" onClick={onClose} style={{ flex: 1 }}>{COPY.CANCEL}</button>
        <button className="btn-primary" onClick={handleSubmit} disabled={loading} style={{ flex: 1 }}>
          {loading ? COPY.CREDITORS_SAVING : COPY.CREDITORS_SAVE}
        </button>
      </div>
    </ModalShell>
  )
}

function CustomerDetailModal({
  customerId,
  onClose,
  onChanged,
}: {
  customerId: string
  onClose: () => void
  onChanged: () => void
}) {
  const [detail, setDetail] = useState<CustomerDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [settling, setSettling] = useState(false)
  const [amount, setAmount] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    return fetchCustomer(customerId).then(setDetail).catch(() => setError(COPY.CREDITORS_LOAD_ERROR)).finally(() => setLoading(false))
  }, [customerId])

  useEffect(() => { load() }, [load])

  async function handleSettle() {
    if (!detail) return
    const amt = parseFloat(amount)
    if (isNaN(amt) || amt <= 0) { setError(COPY.CREDITORS_SETTLE_AMOUNT_ERROR); return }
    setSettling(true)
    setError('')
    try {
      await settleCustomerBalance(detail.id, amount.trim())
      setAmount('')
      await load()
      onChanged()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || COPY.CREDITORS_GENERIC_ERROR)
    } finally {
      setSettling(false)
    }
  }

  return (
    <ModalShell onClose={onClose} title={detail?.name ?? '...'}>
      {loading || !detail ? (
        <div style={{ textAlign: 'center', padding: 'var(--sp-5)', color: 'var(--color-muted)' }}>{COPY.CREDITORS_LOADING}</div>
      ) : (
        <>
          <div className="card-stat" style={{ marginBottom: 'var(--sp-4)' }}>
            <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.CREDITORS_BALANCE}</span>
            <div style={{ fontSize: 'var(--fs-xl)', fontWeight: 700, color: Number(detail.balance) > 0 ? 'var(--color-error)' : 'var(--color-teal)' }}>
              KES {Number(detail.balance).toLocaleString()}
            </div>
          </div>

          {Number(detail.balance) > 0 && (
            <div style={{ marginBottom: 'var(--sp-4)' }}>
              <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                {COPY.CREDITORS_SETTLE_LABEL}
              </label>
              <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
                <input
                  className="input" type="number" min="0" step="any" inputMode="decimal"
                  placeholder="0" value={amount} onChange={(e) => setAmount(e.target.value)}
                  style={{ flex: 1 }}
                />
                <button className="btn-primary" onClick={handleSettle} disabled={settling}>
                  {settling ? COPY.CREDITORS_SAVING : COPY.CREDITORS_SETTLE_BTN}
                </button>
              </div>
              {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-xs)', marginTop: 'var(--sp-2)' }}>{error}</p>}
            </div>
          )}

          <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)', fontWeight: 600 }}>
            {COPY.CREDITORS_SALE_HISTORY}
          </div>
          <div style={{ maxHeight: 240, overflowY: 'auto', marginBottom: 'var(--sp-3)' }}>
            {detail.sales.length === 0 ? (
              <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.CREDITORS_NO_SALES}</p>
            ) : (
              detail.sales.map((s) => (
                <div key={s.id} style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--sp-2) 0', borderBottom: '1px solid var(--surface-3)', fontSize: 'var(--fs-xs)' }}>
                  <span className="mono" style={{ color: 'var(--color-muted)' }}>{s.reference_number}</span>
                  <span>{new Date(s.created_at).toLocaleDateString()}</span>
                  <span style={{ fontWeight: 600 }}>KES {Number(s.total_amount).toLocaleString()}</span>
                </div>
              ))
            )}
          </div>

          {detail.payments.length > 0 && (
            <>
              <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)', fontWeight: 600 }}>
                {COPY.CREDITORS_PAYMENT_HISTORY}
              </div>
              <div style={{ maxHeight: 160, overflowY: 'auto' }}>
                {detail.payments.map((p) => (
                  <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--sp-2) 0', borderBottom: '1px solid var(--surface-3)', fontSize: 'var(--fs-xs)' }}>
                    <span>{new Date(p.created_at).toLocaleDateString()}</span>
                    <span style={{ fontWeight: 600, color: 'var(--color-teal)' }}>KES {Number(p.amount).toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </ModalShell>
  )
}

function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 50,
      background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 'var(--sp-4)',
    }} onClick={onClose}>
      <div
        className="card"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: 460, width: '100%', maxHeight: '85dvh', overflowY: 'auto' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-4)' }}>
          <h2 style={{ fontSize: 'var(--fs-md)', fontWeight: 700 }}>{title}</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-muted)', fontSize: 20 }}>✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}
