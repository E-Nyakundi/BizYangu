'use client'

/**
 * BizYangu — STOCK MODE
 * Stock levels list → drill-down per product (movements log + quick actions).
 * Owner/manager can: add delivery, log loss, submit physical count.
 */

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useAuthStore } from '@/lib/auth'
import {
  listStockLevels,
  listMovements,
  submitStockCount,
  type StockLevel,
  type StockMovement,
} from '@/lib/inventory'
import { createSale } from '@/lib/transactions'
import { createProduct } from '@/lib/catalog'
import { COPY } from '@/lib/copy'

// ── Re-use transactions endpoint for stock-in / adjustment / loss ────────────
// The backend routes these through /transactions/stock-in/ and /adjustment/
import { api } from '@/lib/api'

async function apiStockIn(product_id: string, quantity: string, notes: string) {
  const { data } = await api.post('/transactions/stock-in/', { product_id, quantity, notes })
  return data
}

async function apiLogLoss(product_id: string, quantity_change: string, reason: string, notes: string) {
  const { data } = await api.post('/transactions/loss/', { product_id, quantity_change, reason, notes })
  return data
}

// ── Constants ─────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  OK: 'var(--color-teal)',
  LOW: '#F59E0B',
  OUT: 'var(--color-error)',
}

const STATUS_LABEL: Record<string, string> = {
  OK: COPY.STOCK_STATUS_OK,
  LOW: COPY.STOCK_STATUS_LOW,
  OUT: COPY.STOCK_STATUS_OUT,
}

const MOVEMENT_LABEL: Record<string, string> = {
  SALE: COPY.STOCK_MOVEMENT_SALE,
  RESTOCK: COPY.STOCK_MOVEMENT_RESTOCK,
  ADJUSTMENT: COPY.STOCK_MOVEMENT_ADJUSTMENT,
  LOSS: COPY.STOCK_MOVEMENT_LOSS,
  DAMAGE: COPY.STOCK_MOVEMENT_DAMAGE,
  REFUND: COPY.STOCK_MOVEMENT_REFUND,
  COUNT: COPY.STOCK_MOVEMENT_COUNT,
}

const MOVEMENT_COLOR: Record<string, string> = {
  SALE: 'var(--color-error)',
  LOSS: 'var(--color-error)',
  DAMAGE: 'var(--color-error)',
  RESTOCK: 'var(--color-teal)',
  REFUND: 'var(--color-teal)',
  ADJUSTMENT: 'var(--color-violet)',
  COUNT: 'var(--color-violet)',
}

// ── Modal: Add Delivery ───────────────────────────────────────────────────────

function StockInModal({ product, onClose, onDone }: {
  product: StockLevel
  onClose: () => void
  onDone: () => void
}) {
  const [qty, setQty] = useState('')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit() {
    const q = parseFloat(qty)
    if (isNaN(q) || q <= 0) { setError(COPY.STOCK_VALID_QTY_ERROR); return }
    setLoading(true); setError('')
    try {
      await apiStockIn(product.id, qty, notes.trim())
      onDone()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || COPY.STOCK_GENERIC_ERROR)
      setLoading(false)
    }
  }

  return (
    <Overlay onClose={onClose}>
      <h3 style={{ marginBottom: 'var(--sp-1)' }}>{COPY.STOCK_IN_TITLE}</h3>
      <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-4)' }}>
        {COPY.STOCK_HAS_NOW
          .replace('{name}', product.name)
          .replace('{qty}', '')
          .replace('{unit}', '')}
        <strong>{Number(product.current_stock).toLocaleString()} {product.unit}</strong>
      </p>
      <Field label={COPY.STOCK_QTY_RECEIVED}>
        <input className="input" type="number" min="0.001" step="any" placeholder="0"
          value={qty} onChange={(e) => setQty(e.target.value)} autoFocus style={{ width: '100%' }} />
      </Field>
      <Field label={COPY.STOCK_NOTES_LABEL}>
        <input className="input" type="text" placeholder={COPY.STOCK_SUPPLIER_PLACEHOLDER}
          value={notes} onChange={(e) => setNotes(e.target.value)} style={{ width: '100%' }} />
      </Field>
      {error && <ErrorMsg>{error}</ErrorMsg>}
      <ModalActions onCancel={onClose} onConfirm={handleSubmit} loading={loading}
        confirmLabel={COPY.SAVE} confirmClass="btn-primary" />
    </Overlay>
  )
}

// ── Modal: Log Loss ───────────────────────────────────────────────────────────

const LOSS_REASONS = [
  { key: 'theft', value: 'LOSS', label: COPY.STOCK_LOSS_THEFT },
  { key: 'expiry', value: 'LOSS', label: COPY.STOCK_LOSS_EXPIRY },
  { key: 'damage', value: 'DAMAGE', label: COPY.STOCK_LOSS_DAMAGE },
  { key: 'other', value: 'ADJUSTMENT', label: COPY.STOCK_LOSS_OTHER },
] as const

function LossModal({ product, onClose, onDone }: {
  product: StockLevel
  onClose: () => void
  onDone: () => void
}) {
  const [qty, setQty] = useState('')
  const [selectedKey, setSelectedKey] = useState<string>('theft')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const selected = LOSS_REASONS.find((r) => r.key === selectedKey) ?? LOSS_REASONS[0]

  async function handleSubmit() {
    const q = parseFloat(qty)
    if (isNaN(q) || q <= 0) { setError(COPY.STOCK_VALID_QTY_ERROR); return }
    if (q > Number(product.current_stock)) {
      setError(COPY.STOCK_LOSS_EXCEED_ERROR.replace('{qty}', String(product.current_stock)).replace('{unit}', product.unit)); return
    }
    setLoading(true); setError('')
    try {
      // Reason label is always recorded in notes (e.g. "Theft") so the
      // audit trail keeps the human-readable cause even though the
      // backend only stores a 3-way enum (LOSS / DAMAGE / ADJUSTMENT).
      const combinedNotes = notes.trim() ? `${selected.label} — ${notes.trim()}` : selected.label
      await apiLogLoss(product.id, String(-q), selected.value, combinedNotes)
      onDone()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || COPY.STOCK_GENERIC_ERROR)
      setLoading(false)
    }
  }

  return (
    <Overlay onClose={onClose}>
      <h3 style={{ marginBottom: 'var(--sp-1)' }}>{COPY.STOCK_LOSS_TITLE}</h3>
      <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-4)' }}>
        {product.name} — <strong>{Number(product.current_stock).toLocaleString()} {product.unit}</strong>
      </p>
      <Field label={COPY.STOCK_LOSS_TYPE_LABEL}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)' }}>
          {LOSS_REASONS.map((r) => (
            <button key={r.key} onClick={() => setSelectedKey(r.key)}
              style={{
                padding: 'var(--sp-2)',
                borderRadius: 'var(--radius-default)',
                border: `1px solid ${selectedKey === r.key ? 'var(--color-error)' : 'var(--surface-4)'}`,
                background: selectedKey === r.key ? 'rgba(255,77,109,0.1)' : 'var(--surface-2)',
                color: selectedKey === r.key ? 'var(--color-error)' : 'var(--color-muted)',
                cursor: 'pointer', fontSize: 'var(--fs-xs)', fontFamily: 'var(--font-display)',
              }}>
              {r.label}
            </button>
          ))}
        </div>
      </Field>
      <Field label={COPY.STOCK_QTY_UNIT_LABEL.replace('{unit}', product.unit)}>
        <input className="input" type="number" min="0.001" step="any" placeholder="0"
          value={qty} onChange={(e) => setQty(e.target.value)} style={{ width: '100%' }} />
      </Field>
      <Field label={COPY.STOCK_NOTES_LABEL}>
        <input className="input" type="text" placeholder={COPY.STOCK_LOSS_MORE_DETAILS}
          value={notes} onChange={(e) => setNotes(e.target.value)} style={{ width: '100%' }} />
      </Field>
      {error && <ErrorMsg>{error}</ErrorMsg>}
      <ModalActions onCancel={onClose} onConfirm={handleSubmit} loading={loading}
        confirmLabel={COPY.STOCK_LOSS_SUBMIT} confirmClass="btn-destructive" />
    </Overlay>
  )
}

// ── Modal: Stock Count ────────────────────────────────────────────────────────

function CountModal({ product, onClose, onDone }: {
  product: StockLevel
  onClose: () => void
  onDone: () => void
}) {
  const [counted, setCounted] = useState(product.current_stock)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const diff = parseFloat(counted) - Number(product.current_stock)

  async function handleSubmit() {
    const q = parseFloat(counted)
    if (isNaN(q) || q < 0) { setError(COPY.STOCK_COUNT_INVALID); return }
    setLoading(true); setError('')
    try {
      await submitStockCount({ product_id: product.id, counted_quantity: counted })
      onDone()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || COPY.STOCK_GENERIC_ERROR)
      setLoading(false)
    }
  }

  return (
    <Overlay onClose={onClose}>
      <h3 style={{ marginBottom: 'var(--sp-1)' }}>{COPY.STOCK_COUNT_TITLE}</h3>
      <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-4)' }}>
        {COPY.STOCK_COUNT_SYSTEM_SAYS
          .replace('{name}', product.name)
          .replace('{qty}', '')
          .replace('{unit}', '')}
        <strong>{Number(product.current_stock).toLocaleString()} {product.unit}</strong>
      </p>
      <Field label={COPY.STOCK_COUNT_HOW_MANY.replace('{unit}', product.unit)}>
        <input className="input" type="number" min="0" step="any"
          value={counted} onChange={(e) => setCounted(e.target.value)}
          autoFocus style={{ width: '100%' }} />
      </Field>
      {counted !== '' && !isNaN(parseFloat(counted)) && parseFloat(counted) !== Number(product.current_stock) && (
        <div style={{
          background: diff < 0 ? 'rgba(255,77,109,0.1)' : 'rgba(0,229,196,0.1)',
          border: `1px solid ${diff < 0 ? 'var(--color-error)' : 'var(--color-teal)'}`,
          borderRadius: 'var(--radius-default)', padding: 'var(--sp-3)',
          marginBottom: 'var(--sp-3)', fontSize: 'var(--fs-xs)',
          color: diff < 0 ? 'var(--color-error)' : 'var(--color-teal)',
        }}>
          {COPY.STOCK_COUNT_DIFFERENCE.replace('{diff}', `${diff > 0 ? '+' : ''}${diff.toLocaleString()}`).replace('{unit}', product.unit)}
          {diff < 0 && COPY.STOCK_COUNT_UNKNOWN_LOSS}
          {diff > 0 && COPY.STOCK_COUNT_SURPLUS}
        </div>
      )}
      {error && <ErrorMsg>{error}</ErrorMsg>}
      <ModalActions onCancel={onClose} onConfirm={handleSubmit} loading={loading}
        confirmLabel={COPY.STOCK_COUNT_SUBMIT} confirmClass="btn-primary" />
    </Overlay>
  )
}

// ── Modal: Add new product (progressive onboarding) ──────────────────────────

const UNIT_OPTIONS = ['pcs', 'kg', 'g', 'l', 'ml', 'pack', 'box'] as const

function AddProductModal({ onClose, onDone }: {
  onClose: () => void
  onDone: () => void
}) {
  const [name, setName] = useState('')
  const [price, setPrice] = useState('')
  const [cost, setCost] = useState('')
  const [qty, setQty] = useState('')
  const [threshold, setThreshold] = useState('')
  const [unit, setUnit] = useState<string>('pcs')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [justSaved, setJustSaved] = useState(false)

  function resetForm() {
    setName(''); setPrice(''); setCost(''); setQty(''); setThreshold('')
  }

  async function handleSubmit(addAnother: boolean) {
    if (!name.trim()) { setError(COPY.STOCK_NEW_NAME_ERROR); return }
    const sellingPrice = parseFloat(price)
    if (isNaN(sellingPrice) || sellingPrice <= 0) { setError(COPY.STOCK_NEW_PRICE_ERROR); return }
    setLoading(true); setError('')
    try {
      await createProduct({
        name: name.trim(),
        selling_price: price.trim(),
        cost_price: cost.trim() || undefined,
        current_stock: qty.trim() || '0',
        low_stock_threshold: threshold.trim() || undefined,
        unit,
      })
      onDone()
      if (addAnother) {
        resetForm()
        setLoading(false)
        setJustSaved(true)
        setTimeout(() => setJustSaved(false), 1500)
      } else {
        onClose()
      }
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || COPY.STOCK_GENERIC_ERROR)
      setLoading(false)
    }
  }

  return (
    <Overlay onClose={onClose}>
      <h3 style={{ marginBottom: 'var(--sp-1)' }}>{COPY.STOCK_NEW_PRODUCT_TITLE}</h3>
      <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-4)' }}>
        {COPY.STOCK_NEW_PRODUCT_SUBTITLE}
      </p>

      <Field label={COPY.STOCK_NEW_NAME_LABEL}>
        <input className="input" type="text" placeholder={COPY.STOCK_NEW_NAME_PLACEHOLDER}
          value={name} onChange={(e) => setName(e.target.value)} autoFocus style={{ width: '100%' }} />
      </Field>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)' }}>
        <Field label={COPY.STOCK_NEW_PRICE_LABEL}>
          <input className="input" type="number" min="0" step="any" placeholder="0"
            inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} style={{ width: '100%' }} />
        </Field>
        <Field label={COPY.STOCK_NEW_COST_LABEL}>
          <input className="input" type="number" min="0" step="any" placeholder="0"
            inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value)} style={{ width: '100%' }} />
        </Field>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)' }}>
        <Field label={COPY.STOCK_NEW_QTY_LABEL}>
          <input className="input" type="number" min="0" step="any" placeholder="0"
            inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} style={{ width: '100%' }} />
        </Field>
        <Field label={COPY.STOCK_NEW_THRESHOLD_LABEL}>
          <input className="input" type="number" min="0" step="any" placeholder="0"
            inputMode="decimal" value={threshold} onChange={(e) => setThreshold(e.target.value)} style={{ width: '100%' }} />
        </Field>
      </div>

      <Field label={COPY.STOCK_NEW_UNIT_LABEL}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-2)' }}>
          {UNIT_OPTIONS.map((u) => (
            <button key={u} type="button" onClick={() => setUnit(u)}
              style={{
                padding: 'var(--sp-1) var(--sp-3)',
                borderRadius: 'var(--radius-pill)',
                border: `1px solid ${unit === u ? 'var(--color-teal)' : 'var(--surface-4)'}`,
                background: unit === u ? 'rgba(0,229,196,0.1)' : 'var(--surface-2)',
                color: unit === u ? 'var(--color-teal)' : 'var(--color-muted)',
                cursor: 'pointer', fontSize: 'var(--fs-xs)', fontFamily: 'var(--font-display)',
              }}>
              {u}
            </button>
          ))}
        </div>
      </Field>

      {justSaved && (
        <div style={{
          background: 'rgba(0,229,196,0.1)', border: '1px solid var(--color-teal)',
          borderRadius: 'var(--radius-default)', padding: 'var(--sp-3)',
          marginBottom: 'var(--sp-3)', fontSize: 'var(--fs-xs)', color: 'var(--color-teal)',
        }}>
          {COPY.STOCK_NEW_SAVED_TOAST}
        </div>
      )}
      {error && <ErrorMsg>{error}</ErrorMsg>}

      <div style={{ display: 'flex', gap: 'var(--sp-3)', marginTop: 'var(--sp-2)' }}>
        <button className="btn-ghost" onClick={onClose} disabled={loading} style={{ flex: 1 }}>{COPY.CANCEL}</button>
        <button className="btn-secondary" onClick={() => handleSubmit(true)} disabled={loading} style={{ flex: 1 }}>
          {loading ? COPY.STOCK_SAVING : COPY.STOCK_NEW_SAVE_ANOTHER}
        </button>
        <button className="btn-primary" onClick={() => handleSubmit(false)} disabled={loading} style={{ flex: 1 }}>
          {loading ? COPY.STOCK_SAVING : COPY.STOCK_NEW_SUBMIT}
        </button>
      </div>
    </Overlay>
  )
}

// ── Product drawer — movements + quick actions ────────────────────────────────

function ProductDrawer({
  product,
  canWrite,
  onClose,
  onRefresh,
}: {
  product: StockLevel
  canWrite: boolean
  onClose: () => void
  onRefresh: () => void
}) {
  const [modal, setModal] = useState<'stock-in' | 'loss' | 'count' | null>(null)
  const [movements, setMovements] = useState<StockMovement[]>([])
  const [loadingMov, setLoadingMov] = useState(true)
  // Mount closed, then flip to open a frame later so the transform
  // transition below actually has something to animate from → to.
  const [entered, setEntered] = useState(false)

  useEffect(() => {
    const id = requestAnimationFrame(() => setEntered(true))
    return () => cancelAnimationFrame(id)
  }, [])

  useEffect(() => {
    listMovements({ product: product.id, page: 1 })
      .then((r) => setMovements(r.results))
      .catch(() => {})
      .finally(() => setLoadingMov(false))
  }, [product.id])

  function handleModalDone() {
    setModal(null)
    onRefresh()
    // Refresh movements too
    setLoadingMov(true)
    listMovements({ product: product.id, page: 1 })
      .then((r) => setMovements(r.results))
      .finally(() => setLoadingMov(false))
  }

  // Play the exit transition before actually unmounting.
  function handleClose() {
    setEntered(false)
    setTimeout(onClose, 220)
  }

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={handleClose}
        className={`stock-drawer-backdrop${entered ? ' drawer-open' : ''}`}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 40 }}
      />

      {/* Drawer */}
      <div className={`stock-drawer${entered ? ' drawer-open' : ''}`} style={{
        position: 'fixed', right: 0, top: 0, bottom: 0, width: 380, maxWidth: '90vw',
        background: 'var(--surface-1)', borderLeft: '1px solid var(--surface-2)',
        zIndex: 50, display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        {/* Mobile drag handle */}
        <div className="stock-drawer-handle" style={{
          display: 'none', width: 36, height: 4, borderRadius: 99,
          background: 'var(--surface-4)', margin: 'var(--sp-2) auto 0',
        }} />
        {/* Header */}
        <div style={{ padding: 'var(--sp-4)', borderBottom: '1px solid var(--surface-2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <h3 style={{ marginBottom: 2 }}>{product.name}</h3>
              <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{product.sku}</span>
            </div>
            <button onClick={handleClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-muted)', fontSize: 20 }}>×</button>
          </div>

          {/* Stock stat */}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--sp-2)', marginTop: 'var(--sp-3)' }}>
            <span style={{ fontSize: 'var(--fs-lg)', fontWeight: 700, color: STATUS_COLOR[product.stock_status] }}>
              {Number(product.current_stock).toLocaleString()}
            </span>
            <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{product.unit}</span>
            <span className={`badge ${product.stock_status === 'OK' ? 'badge-active' : 'badge-error'}`} style={{ fontSize: 'var(--fs-xs)' }}>
              {STATUS_LABEL[product.stock_status]}
            </span>
          </div>
          <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginTop: 2 }}>
            {COPY.STOCK_DRAWER_MIN_THRESHOLD
              .replace('{qty}', Number(product.low_stock_threshold).toLocaleString())
              .replace('{unit}', product.unit)}
          </div>
        </div>

        {/* Quick actions */}
        {canWrite && (
          <div style={{ padding: 'var(--sp-4)', borderBottom: '1px solid var(--surface-2)', display: 'flex', gap: 'var(--sp-2)' }}>
            <button className="btn-primary btn-sm" onClick={() => setModal('stock-in')} style={{ flex: 1 }}>
              {COPY.STOCK_DRAWER_ADD_STOCK}
            </button>
            <button className="btn-destructive btn-sm" onClick={() => setModal('loss')} style={{ flex: 1 }}>
              {COPY.STOCK_MOVEMENT_LOSS}
            </button>
            <button className="btn-secondary btn-sm" onClick={() => setModal('count')} style={{ flex: 1 }}>
              {COPY.STOCK_COUNT}
            </button>
          </div>
        )}

        {/* Movement log */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--sp-4)' }}>
          <p className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-3)' }}>
            {COPY.STOCK_DRAWER_HISTORY_LABEL}
          </p>

          {loadingMov ? (
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.LOADING}</p>
          ) : movements.length === 0 ? (
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.EMPTY_STOCK_HISTORY}</p>
          ) : (
            movements.map((mv) => (
              <div key={mv.id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                paddingBottom: 'var(--sp-3)', marginBottom: 'var(--sp-3)',
                borderBottom: '1px solid var(--surface-2)',
              }}>
                <div>
                  <span className="badge badge-muted" style={{ fontSize: 'var(--fs-xs)', marginBottom: 2, display: 'inline-block' }}>
                    {MOVEMENT_LABEL[mv.movement_type] || mv.movement_type}
                  </span>
                  <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                    {new Date(mv.created_at).toLocaleString('en-KE', { dateStyle: 'short', timeStyle: 'short' })}
                    {' · '}{mv.created_by_name}
                  </div>
                  {mv.notes && (
                    <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginTop: 2, fontStyle: 'italic' }}>
                      {mv.notes}
                    </div>
                  )}
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontWeight: 700, color: MOVEMENT_COLOR[mv.movement_type], fontSize: 'var(--fs-sm)' }}>
                    {Number(mv.quantity_change) >= 0 ? '+' : ''}{Number(mv.quantity_change).toLocaleString()}
                  </div>
                  <div className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                    → {Number(mv.quantity_after).toLocaleString()}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Modals */}
      {modal === 'stock-in' && (
        <StockInModal product={product} onClose={() => setModal(null)} onDone={handleModalDone} />
      )}
      {modal === 'loss' && (
        <LossModal product={product} onClose={() => setModal(null)} onDone={handleModalDone} />
      )}
      {modal === 'count' && (
        <CountModal product={product} onClose={() => setModal(null)} onDone={handleModalDone} />
      )}
    </>
  )
}

// ── Main STOCK MODE page ──────────────────────────────────────────────────────

export default function StockPage() {
  const user = useAuthStore((s) => s.user)
  const canWrite = user?.role === 'OWNER' || user?.role === 'MANAGER'

  const [stockLevels, setStockLevels] = useState<StockLevel[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<'ALL' | 'LOW' | 'OUT'>('ALL')
  const [selected, setSelected] = useState<StockLevel | null>(null)
  const [showAddProduct, setShowAddProduct] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listStockLevels(search ? { q: search } : {})
      setStockLevels(data)
    } catch {/* swallow */}
    finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])

  // Counts for filter tabs
  const lowCount = stockLevels.filter((p) => p.stock_status === 'LOW').length
  const outCount = stockLevels.filter((p) => p.stock_status === 'OUT').length

  const visible = stockLevels.filter((p) => {
    if (filter === 'LOW') return p.stock_status === 'LOW'
    if (filter === 'OUT') return p.stock_status === 'OUT'
    return true
  })

  return (
    <div style={{ minHeight: '100dvh', background: 'var(--surface-0)' }}>

      {/* Header */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: 'var(--sp-3) var(--sp-4)',
        borderBottom: '1px solid var(--surface-2)',
        background: 'var(--surface-1)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <span className="mono" style={{ color: 'var(--color-teal)', fontSize: 'var(--fs-xs)' }}>{COPY.STOCK_MODE_LABEL}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
          {canWrite && (
            <button className="btn-secondary btn-sm" onClick={() => setShowAddProduct(true)} style={{ fontSize: 'var(--fs-xs)' }}>
              {COPY.STOCK_ADD_NEW}
            </button>
          )}
          <Link href="/dashboard" className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }}>{COPY.STOCK_GO_HOME}</Link>
        </div>
      </header>

      <main data-main style={{ maxWidth: 800, margin: '0 auto', padding: 'var(--sp-5) var(--sp-4)' }}>

        {/* Search */}
        <input
          className="input"
          type="search"
          placeholder={COPY.STOCK_SEARCH}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: '100%', marginBottom: 'var(--sp-4)' }}
        />

        {/* Filter tabs */}
        <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
          {(['ALL', 'LOW', 'OUT'] as const).map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              style={{
                padding: 'var(--sp-1) var(--sp-3)',
                borderRadius: 'var(--radius-pill)',
                border: `1px solid ${filter === f ? 'var(--color-teal)' : 'var(--surface-4)'}`,
                background: filter === f ? 'rgba(0,229,196,0.1)' : 'var(--surface-2)',
                color: filter === f ? 'var(--color-teal)' : 'var(--color-muted)',
                cursor: 'pointer', fontSize: 'var(--fs-xs)', fontFamily: 'var(--font-display)',
              }}>
              {f === 'ALL' ? COPY.STOCK_FILTER_ALL_COUNT.replace('{count}', String(stockLevels.length))
                : f === 'LOW' ? COPY.STOCK_FILTER_LOW_COUNT.replace('{count}', String(lowCount))
                : COPY.STOCK_FILTER_OUT_COUNT.replace('{count}', String(outCount))}
            </button>
          ))}
        </div>

        {/* Summary strip */}
        {!loading && (outCount > 0 || lowCount > 0) && (
          <div style={{
            background: 'rgba(255,77,109,0.08)', border: '1px solid rgba(255,77,109,0.3)',
            borderRadius: 'var(--radius-card)', padding: 'var(--sp-3) var(--sp-4)',
            marginBottom: 'var(--sp-4)', display: 'flex', gap: 'var(--sp-4)',
          }}>
            {outCount > 0 && (
              <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-error)' }}>
                {COPY.STOCK_OUT_SUMMARY.replace('{count}', String(outCount))}
              </span>
            )}
            {lowCount > 0 && (
              <span style={{ fontSize: 'var(--fs-xs)', color: '#F59E0B' }}>
                {COPY.STOCK_LOW_SUMMARY.replace('{count}', String(lowCount))}
              </span>
            )}
          </div>
        )}

        {/* Stock list */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: 'var(--sp-7)', color: 'var(--color-muted)' }}>{COPY.STOCK_LOADING}</div>
        ) : visible.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 'var(--sp-7)', color: 'var(--color-muted)' }}>
            {search ? COPY.STOCK_EMPTY_SEARCH.replace('{search}', search) : filter !== 'ALL' ? COPY.STOCK_EMPTY_FILTER : COPY.STOCK_EMPTY_NONE}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
            {visible.map((p) => (
              <div key={p.id}
                onClick={() => setSelected(p)}
                style={{
                  background: 'var(--surface-2)', borderRadius: 'var(--radius-card)',
                  padding: 'var(--sp-3) var(--sp-4)',
                  border: `1px solid ${p.stock_status === 'OUT' ? 'rgba(255,77,109,0.3)' : p.stock_status === 'LOW' ? 'rgba(245,158,11,0.3)' : 'var(--surface-3)'}`,
                  cursor: 'pointer', transition: 'border-color 0.15s',
                  display: 'flex', alignItems: 'center', gap: 'var(--sp-4)',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-teal)')}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = p.stock_status === 'OUT' ? 'rgba(255,77,109,0.3)' : p.stock_status === 'LOW' ? 'rgba(245,158,11,0.3)' : 'var(--surface-3)')}
              >
                {/* Status bar */}
                <div style={{ width: 3, borderRadius: 99, alignSelf: 'stretch', background: STATUS_COLOR[p.stock_status], flexShrink: 0 }} />

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 'var(--fs-sm)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.name}
                  </div>
                  <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                    {p.category_name && `${p.category_name} · `}{p.sku}
                  </div>
                </div>

                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 'var(--fs-md)', color: STATUS_COLOR[p.stock_status] }}>
                    {Number(p.current_stock).toLocaleString()}
                  </div>
                  <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                    {p.unit} · min {Number(p.low_stock_threshold).toLocaleString()}
                  </div>
                </div>

                <div style={{ color: 'var(--color-muted)', fontSize: 18, flexShrink: 0 }}>›</div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Product drawer */}
      {selected && (
        <ProductDrawer
          product={selected}
          canWrite={canWrite}
          onClose={() => setSelected(null)}
          onRefresh={() => {
            load()
            // Update selected product in-place so drawer reflects new stock
            listStockLevels().then((updated) => {
              const fresh = updated.find((p) => p.id === selected.id)
              if (fresh) setSelected(fresh)
            }).catch(() => {})
          }}
        />
      )}

      {/* Floating "add product" button — mobile-first continuous onboarding */}
      {canWrite && (
        <button
          className="stock-fab"
          onClick={() => setShowAddProduct(true)}
          aria-label={COPY.STOCK_ADD_NEW}
          style={{
            position: 'fixed',
            right: 'var(--sp-4)',
            bottom: 'calc(64px + env(safe-area-inset-bottom) + var(--sp-4))',
            zIndex: 20,
            display: 'flex', alignItems: 'center', gap: 'var(--sp-2)',
            background: 'var(--color-teal)', color: 'var(--surface-0)',
            border: 'none', borderRadius: 'var(--radius-pill)',
            padding: 'var(--sp-3) var(--sp-4)', cursor: 'pointer',
            fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 'var(--fs-sm)',
            boxShadow: '0 6px 20px rgba(0,0,0,0.45)',
          }}
        >
          {COPY.STOCK_ADD_NEW}
        </button>
      )}

      {showAddProduct && (
        <AddProductModal
          onClose={() => setShowAddProduct(false)}
          onDone={load}
        />
      )}

      <style>{`
        /* Product drawer: slide in from the right on desktop, up from the
           bottom on mobile — mirrors .sell-cart-panel on the Sell page. */
        .stock-drawer-backdrop {
          opacity: 0;
          transition: opacity 0.22s ease;
        }
        .stock-drawer-backdrop.drawer-open {
          opacity: 1;
        }
        .stock-drawer {
          transform: translateX(100%);
          transition: transform 0.25s ease;
        }
        .stock-drawer.drawer-open {
          transform: translateX(0);
        }

        @media (max-width: 767px) {
          .stock-drawer {
            left: 0;
            right: 0;
            top: auto !important;
            bottom: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            height: 85dvh;
            max-height: 85dvh;
            border-left: none !important;
            border-top: 1px solid var(--surface-2);
            border-radius: var(--radius-card) var(--radius-card) 0 0;
            transform: translateY(100%);
          }
          .stock-drawer.drawer-open {
            transform: translateY(0);
          }
          .stock-drawer-handle {
            display: block !important;
          }
          .stock-fab {
            bottom: calc(64px + env(safe-area-inset-bottom) + var(--sp-3)) !important;
          }
        }
      `}</style>
    </div>
  )
}

// ── Shared micro-components ───────────────────────────────────────────────────

function Overlay({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 100, padding: 'var(--sp-5)',
      animation: 'stock-overlay-fade 0.18s ease',
    }}>
      <div onClick={(e) => e.stopPropagation()}
        className="card"
        style={{
          maxWidth: 420, width: '100%', maxHeight: '90dvh', overflowY: 'auto',
          animation: 'stock-modal-in 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        }}>
        {children}
      </div>
      <style>{`
        @keyframes stock-overlay-fade {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes stock-modal-in {
          from { opacity: 0; transform: translateY(8px) scale(0.97); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 'var(--sp-3)' }}>
      <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
        {label}
      </label>
      {children}
    </div>
  )
}

function ErrorMsg({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      background: 'rgba(255,77,109,0.1)', border: '1px solid var(--color-error)',
      borderRadius: 'var(--radius-default)', padding: 'var(--sp-3)',
      marginBottom: 'var(--sp-3)', fontSize: 'var(--fs-xs)', color: 'var(--color-error)',
    }}>
      {children}
    </div>
  )
}

function ModalActions({ onCancel, onConfirm, loading, confirmLabel, confirmClass }: {
  onCancel: () => void
  onConfirm: () => void
  loading: boolean
  confirmLabel: string
  confirmClass: string
}) {
  return (
    <div style={{ display: 'flex', gap: 'var(--sp-3)', marginTop: 'var(--sp-2)' }}>
      <button className="btn-ghost" onClick={onCancel} disabled={loading} style={{ flex: 1 }}>{COPY.CANCEL}</button>
      <button className={confirmClass} onClick={onConfirm} disabled={loading} style={{ flex: 1 }}>
        {loading ? COPY.STOCK_SAVING : confirmLabel}
      </button>
    </div>
  )
}
