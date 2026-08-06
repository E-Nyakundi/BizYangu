'use client'

import { useEffect, useState } from 'react'
import { COPY } from '@/lib/copy'
import { PRODUCT_UNITS, productUnitLabel } from '@/lib/knowledge'
import {
  createProductUnit,
  deleteProductUnit,
  listProductUnits,
  updateProductUnit,
  type ProductUnitPayload,
} from '@/lib/catalog'
import type { ProductUnit } from '@/lib/types'

type ProductLike = { id: string }

function t(key: keyof typeof COPY, vars?: Record<string, string | number>) {
  let str = COPY[key] as string
  if (vars) {
    for (const [k, v] of Object.entries(vars)) str = str.replace(`{${k}}`, String(v))
  }
  return str
}

function Overlay({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
        display: 'flex', alignItems: 'flex-end', justifyContent: 'center', zIndex: 200,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--surface-1)', borderRadius: 'var(--radius-card) var(--radius-card) 0 0',
          padding: 'var(--sp-4)', width: '100%', maxWidth: 480, maxHeight: '88vh', overflowY: 'auto',
        }}
      >
        {children}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 'var(--sp-3)' }}>
      <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6, color: 'var(--text-secondary)' }}>
        {label}
      </label>
      {children}
    </div>
  )
}

function ErrorMsg({ text }: { text: string }) {
  return <p style={{ color: 'var(--color-error)', fontSize: 13, marginTop: 6 }}>{text}</p>
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)',
  background: 'var(--surface-2)', fontSize: 15,
}

interface AddUnitModalProps {
  product: ProductLike
  units: ProductUnit[]
  onClose: () => void
  onSaved: (unit: ProductUnit) => void
  editing?: ProductUnit | null
}

function AddUnitModal({ product, units, onClose, onSaved, editing }: AddUnitModalProps) {
  const root = units.find((u) => u.is_root)
  const [parentId, setParentId] = useState(editing?.parent ?? root?.id ?? '')
  const [unit, setUnit] = useState(editing?.unit ?? '')
  const [kind, setKind] = useState<'shared' | 'repackaged'>(editing?.is_repackaged ? 'repackaged' : 'shared')
  const [ratio, setRatio] = useState(editing?.ratio_to_parent ?? '')
  const [price, setPrice] = useState(editing?.selling_price ?? '')
  const [sellable, setSellable] = useState(editing?.is_sellable ?? true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const parent = units.find((u) => u.id === parentId)

  async function handleSave() {
    if (!unit) {
      setError(t('UNITS_GENERIC_ERROR'))
      return
    }
    setSaving(true)
    setError('')
    const payload: Partial<ProductUnitPayload> = {
      unit,
      parent: parentId || null,
      ratio_to_parent: ratio || null,
      is_repackaged: kind === 'repackaged',
      selling_price: price || null,
      is_sellable: sellable,
    }
    try {
      const saved = editing
        ? await updateProductUnit(product.id, editing.id, payload)
        : await createProductUnit(product.id, payload as ProductUnitPayload)
      onSaved(saved)
      onClose()
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? t('UNITS_GENERIC_ERROR'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Overlay onClose={onClose}>
      <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>{t('UNITS_ADD_FORM_TITLE')}</h3>

      <Field label={t('UNITS_PARENT_LABEL')}>
        <select style={inputStyle} value={parentId} onChange={(e) => setParentId(e.target.value)}>
          {units.map((u) => (
            <option key={u.id} value={u.id}>
              {u.is_root ? t('UNITS_ROOT_LABEL') : productUnitLabel(u.unit)}
            </option>
          ))}
        </select>
      </Field>

      <Field label={t('UNITS_UNIT_LABEL')}>
        <select style={inputStyle} value={unit} onChange={(e) => setUnit(e.target.value)}>
          <option value="">—</option>
          {PRODUCT_UNITS.map((u) => (
            <option key={u.id} value={u.id}>{u.label}</option>
          ))}
        </select>
      </Field>

      <Field label={t('UNITS_KIND_LABEL')}>
        <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 8, fontSize: 14 }}>
          <input type="radio" checked={kind === 'shared'} onChange={() => setKind('shared')} style={{ marginTop: 3 }} />
          <span>{t('UNITS_KIND_SHARED')}</span>
        </label>
        <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 14 }}>
          <input type="radio" checked={kind === 'repackaged'} onChange={() => setKind('repackaged')} style={{ marginTop: 3 }} />
          <span>{t('UNITS_KIND_REPACKAGED')}</span>
        </label>
      </Field>

      <Field label={t('UNITS_RATIO_LABEL', { unit: unit ? productUnitLabel(unit) : '' })}>
        <input
          style={inputStyle} inputMode="decimal" placeholder="e.g. 1000"
          value={ratio} onChange={(e) => setRatio(e.target.value)}
        />
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{t('UNITS_RATIO_HELP')}</p>
      </Field>

      <Field label={t('UNITS_PRICE_LABEL')}>
        <input
          style={inputStyle} inputMode="decimal" placeholder="KES"
          value={price} onChange={(e) => setPrice(e.target.value)}
        />
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{t('UNITS_PRICE_HELP')}</p>
      </Field>

      <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 'var(--sp-3)', fontSize: 14 }}>
        <input type="checkbox" checked={sellable} onChange={(e) => setSellable(e.target.checked)} />
        {t('UNITS_SELLABLE_LABEL')}
      </label>

      {error && <ErrorMsg text={error} />}

      <div style={{ display: 'flex', gap: 8, marginTop: 'var(--sp-3)' }}>
        <button
          onClick={handleSave} disabled={saving}
          style={{
            flex: 1, padding: '12px', borderRadius: 12, border: 'none',
            background: 'var(--color-teal)', color: '#fff', fontWeight: 700, fontSize: 15,
          }}
        >
          {saving ? t('UNITS_SAVING') : t('UNITS_SAVE')}
        </button>
        <button
          onClick={onClose}
          style={{ padding: '12px 20px', borderRadius: 12, border: '1px solid var(--border)', background: 'transparent' }}
        >
          Cancel
        </button>
      </div>
    </Overlay>
  )
}

function UnitRow({
  unit, depth, onEdit, onDelete,
}: {
  unit: ProductUnit; depth: number; onEdit: () => void; onDelete: () => void
}) {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 12px', marginLeft: depth * 16,
        background: 'var(--surface-2)', borderRadius: 10, marginBottom: 6,
      }}
    >
      <div>
        <div style={{ fontWeight: 600, fontSize: 14 }}>
          {unit.is_root ? t('UNITS_ROOT_LABEL') : productUnitLabel(unit.unit)}
          {!unit.is_root && (
            <span
              style={{
                marginLeft: 8, fontSize: 11, fontWeight: 600, padding: '2px 6px', borderRadius: 6,
                background: unit.is_repackaged ? 'var(--color-violet-10, rgba(139,92,246,0.12))' : 'var(--color-teal-10, rgba(20,184,166,0.12))',
                color: unit.is_repackaged ? 'var(--color-violet)' : 'var(--color-teal)',
              }}
            >
              {unit.is_repackaged ? '↻' : '='}
            </span>
          )}
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
          {t('UNITS_AVAILABLE', { qty: unit.available_quantity, unit: productUnitLabel(unit.unit) })}
          {unit.selling_price ? ` · KES ${unit.selling_price}` : ''}
        </div>
      </div>
      {!unit.is_root && (
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={onEdit} style={{ fontSize: 13, padding: '6px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'transparent' }}>
            ✎
          </button>
          <button onClick={onDelete} style={{ fontSize: 13, padding: '6px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'transparent', color: 'var(--color-error)' }}>
            {t('UNITS_DELETE')}
          </button>
        </div>
      )}
    </div>
  )
}

export default function ProductUnitManager({ product }: { product: ProductLike }) {
  const [units, setUnits] = useState<ProductUnit[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [editing, setEditing] = useState<ProductUnit | null>(null)

  async function load() {
    setLoading(true)
    setError('')
    try {
      setUnits(await listProductUnits(product.id))
    } catch {
      setError(t('UNITS_GENERIC_ERROR'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product.id])

  function handleSaved(unit: ProductUnit) {
    setUnits((prev) => {
      const exists = prev.some((u) => u.id === unit.id)
      return exists ? prev.map((u) => (u.id === unit.id ? unit : u)) : [...prev, unit]
    })
  }

  async function handleDelete(unit: ProductUnit) {
    const hasChildren = units.some((u) => u.parent === unit.id)
    if (hasChildren) {
      setError(t('UNITS_CANNOT_DELETE_HAS_CHILDREN'))
      return
    }
    if (!confirm(t('UNITS_DELETE_CONFIRM'))) return
    try {
      await deleteProductUnit(product.id, unit.id)
      setUnits((prev) => prev.filter((u) => u.id !== unit.id))
    } catch {
      setError(t('UNITS_GENERIC_ERROR'))
    }
  }

  function renderTree(parentId: string | null, depth: number): React.ReactNode {
    return units
      .filter((u) => u.parent === parentId)
      .map((u) => (
        <div key={u.id}>
          <UnitRow
            unit={u} depth={depth}
            onEdit={() => setEditing(u)}
            onDelete={() => handleDelete(u)}
          />
          {renderTree(u.id, depth + 1)}
        </div>
      ))
  }

  const root = units.find((u) => u.is_root)
  const hasExtras = units.length > 1

  return (
    <div>
      <div style={{ marginBottom: 'var(--sp-3)' }}>
        <h3 style={{ fontSize: 16, fontWeight: 700 }}>{t('UNITS_TITLE')}</h3>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{t('UNITS_SUBTITLE')}</p>
      </div>

      {loading ? (
        <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>...</p>
      ) : (
        <>
          {root && renderTree(null, 0)}
          {!hasExtras && <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{t('UNITS_EMPTY')}</p>}
          {error && <ErrorMsg text={error} />}
          <button
            onClick={() => setShowAdd(true)}
            style={{
              marginTop: 8, fontSize: 14, fontWeight: 600, padding: '10px 14px',
              borderRadius: 10, border: '1px dashed var(--border)', background: 'transparent', width: '100%',
            }}
          >
            {t('UNITS_ADD_FORM')}
          </button>
        </>
      )}

      {showAdd && (
        <AddUnitModal
          product={product} units={units}
          onClose={() => setShowAdd(false)}
          onSaved={handleSaved}
        />
      )}
      {editing && (
        <AddUnitModal
          product={product} units={units} editing={editing}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
