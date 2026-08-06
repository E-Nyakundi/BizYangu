'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useAuthStore } from '@/lib/auth'
import { listProducts, listProductUnits } from '@/lib/catalog'
import { createRepackageEvent, listRepackageEvents } from '@/lib/inventory'
import { productUnitLabel } from '@/lib/knowledge'
import type { Product, ProductUnit, RepackageEvent } from '@/lib/types'
import { COPY } from '@/lib/copy'

function t(key: keyof typeof COPY, vars?: Record<string, string | number>) {
  let str = COPY[key] as string
  if (vars) for (const [k, v] of Object.entries(vars)) str = str.replace(`{${k}}`, String(v))
  return str
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)',
  background: 'var(--surface-2)', fontSize: 15,
}

export default function RepackagePage() {
  const user = useAuthStore((s) => s.user)
  const canWrite = user?.role === 'OWNER' || user?.role === 'MANAGER'

  const [products, setProducts] = useState<Product[]>([])
  const [productId, setProductId] = useState('')
  const [units, setUnits] = useState<ProductUnit[]>([])
  const [fromId, setFromId] = useState('')
  const [toId, setToId] = useState('')
  const [consumed, setConsumed] = useState('')
  const [produced, setProduced] = useState('')
  const [notes, setNotes] = useState('')
  const [history, setHistory] = useState<RepackageEvent[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    listProducts().then(setProducts).catch(() => {})
  }, [])

  useEffect(() => {
    setUnits([])
    setFromId('')
    setToId('')
    setHistory([])
    if (!productId) return
    listProductUnits(productId).then(setUnits).catch(() => {})
    listRepackageEvents(productId).then(setHistory).catch(() => {})
  }, [productId])

  // Anything that has at least one repackaged child can be a "from" — a
  // shared-pool node (pack/stick) never has its own physical repackage
  // event, so it's excluded as a source.
  const fromOptions = useMemo(
    () => units.filter((u) => units.some((c) => c.parent === u.id && c.is_repackaged)),
    [units],
  )
  const toOptions = useMemo(
    () => units.filter((u) => u.parent === fromId && u.is_repackaged),
    [units, fromId],
  )

  const fromUnit = units.find((u) => u.id === fromId)
  const toUnit = units.find((u) => u.id === toId)
  const expectedYield = toUnit?.ratio_to_parent && consumed
    ? (parseFloat(consumed) * parseFloat(toUnit.ratio_to_parent)).toFixed(2)
    : null
  const loss = expectedYield && produced
    ? (parseFloat(expectedYield) - parseFloat(produced)).toFixed(2)
    : null

  async function handleSubmit() {
    if (!fromId || !toId || !consumed || !produced) return
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const event = await createRepackageEvent({
        from_unit_id: fromId, to_unit_id: toId,
        quantity_consumed: consumed, quantity_produced: produced,
        notes: notes || undefined,
      })
      setSuccess(t('REPACKAGE_SUCCESS', {
        produced, to_unit: productUnitLabel(toUnit?.unit ?? ''),
        consumed, from_unit: productUnitLabel(fromUnit?.unit ?? ''),
      }))
      setHistory((prev) => [event, ...prev])
      setConsumed('')
      setProduced('')
      setNotes('')
      // Refresh units so available_quantity reflects the new stock split.
      listProductUnits(productId).then(setUnits).catch(() => {})
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? t('REPACKAGE_GENERIC_ERROR'))
    } finally {
      setSubmitting(false)
    }
  }

  if (!canWrite) {
    return (
      <main data-main style={{ maxWidth: 480, margin: '0 auto', padding: 'var(--sp-5) var(--sp-4)' }}>
        <p>{COPY.PAYMENTS_OWNER_ONLY}</p>
        <Link href="/dashboard" className="btn-ghost">{COPY.STOCK_GO_HOME}</Link>
      </main>
    )
  }

  return (
    <>
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: 'var(--sp-3) var(--sp-4)', borderBottom: '1px solid var(--surface-2)',
        background: 'var(--surface-1)', position: 'sticky', top: 0, zIndex: 10,
      }}>
        <span className="mono" style={{ color: 'var(--color-teal)', fontSize: 'var(--fs-xs)' }}>{t('REPACKAGE_TITLE')}</span>
        <Link href="/stock" className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }}>{COPY.STOCK_GO_HOME}</Link>
      </header>

      <main data-main style={{ maxWidth: 560, margin: '0 auto', padding: 'var(--sp-5) var(--sp-4)' }}>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 'var(--sp-4)' }}>{t('REPACKAGE_SUBTITLE')}</p>

        <div style={{ marginBottom: 'var(--sp-3)' }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{t('REPACKAGE_PRODUCT_LABEL')}</label>
          <select style={inputStyle} value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="">—</option>
            {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>

        {productId && fromOptions.length === 0 && (
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{t('REPACKAGE_NO_TARGETS')}</p>
        )}

        {fromOptions.length > 0 && (
          <>
            <div style={{ marginBottom: 'var(--sp-3)' }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{t('REPACKAGE_FROM_LABEL')}</label>
              <select style={inputStyle} value={fromId} onChange={(e) => { setFromId(e.target.value); setToId('') }}>
                <option value="">—</option>
                {fromOptions.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.is_root ? t('UNITS_ROOT_LABEL') : productUnitLabel(u.unit)} ({u.available_quantity})
                  </option>
                ))}
              </select>
            </div>

            {fromId && (
              <div style={{ marginBottom: 'var(--sp-3)' }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{t('REPACKAGE_TO_LABEL')}</label>
                <select style={inputStyle} value={toId} onChange={(e) => setToId(e.target.value)}>
                  <option value="">—</option>
                  {toOptions.map((u) => (
                    <option key={u.id} value={u.id}>{productUnitLabel(u.unit)}</option>
                  ))}
                </select>
              </div>
            )}

            {toId && (
              <>
                <div style={{ marginBottom: 'var(--sp-3)' }}>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                    {t('REPACKAGE_CONSUMED_LABEL', { unit: productUnitLabel(fromUnit?.unit ?? '') })}
                  </label>
                  <input style={inputStyle} inputMode="decimal" value={consumed} onChange={(e) => setConsumed(e.target.value)} />
                </div>

                <div style={{ marginBottom: 'var(--sp-3)' }}>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                    {t('REPACKAGE_PRODUCED_LABEL', { unit: productUnitLabel(toUnit?.unit ?? '') })}
                  </label>
                  <input style={inputStyle} inputMode="decimal" value={produced} onChange={(e) => setProduced(e.target.value)} />
                  {expectedYield && (
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                      {t('REPACKAGE_EXPECTED_YIELD', { qty: expectedYield, unit: productUnitLabel(toUnit?.unit ?? '') })}
                      {loss && parseFloat(loss) > 0 && ` · ${t('REPACKAGE_LOSS_PREVIEW', { qty: loss, unit: productUnitLabel(toUnit?.unit ?? '') })}`}
                    </p>
                  )}
                </div>

                <div style={{ marginBottom: 'var(--sp-3)' }}>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{t('REPACKAGE_NOTES_LABEL')}</label>
                  <input style={inputStyle} value={notes} onChange={(e) => setNotes(e.target.value)} />
                </div>

                {error && <p style={{ color: 'var(--color-error)', fontSize: 13, marginBottom: 8 }}>{error}</p>}
                {success && <p style={{ color: 'var(--color-teal)', fontSize: 13, marginBottom: 8 }}>{success}</p>}

                <button
                  onClick={handleSubmit}
                  disabled={submitting || !consumed || !produced}
                  style={{
                    width: '100%', padding: '14px', borderRadius: 12, border: 'none',
                    background: 'var(--color-teal)', color: '#fff', fontWeight: 700, fontSize: 15,
                    opacity: submitting || !consumed || !produced ? 0.6 : 1,
                  }}
                >
                  {submitting ? t('REPACKAGE_SUBMITTING') : t('REPACKAGE_SUBMIT')}
                </button>
              </>
            )}
          </>
        )}

        {productId && (
          <div style={{ marginTop: 'var(--sp-5)' }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 8 }}>{t('REPACKAGE_HISTORY_TITLE')}</h3>
            {history.length === 0 ? (
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{t('REPACKAGE_HISTORY_EMPTY')}</p>
            ) : (
              history.map((h) => (
                <div key={h.id} style={{ padding: '8px 12px', background: 'var(--surface-2)', borderRadius: 10, marginBottom: 6, fontSize: 13 }}>
                  {t('REPACKAGE_HISTORY_ROW', { from_unit: h.from_unit_label, to_unit: h.to_unit_label, produced: h.quantity_produced })}
                  <span style={{ color: 'var(--text-secondary)' }}> · {new Date(h.created_at).toLocaleDateString()}</span>
                </div>
              ))
            )}
          </div>
        )}
      </main>
    </>
  )
}
