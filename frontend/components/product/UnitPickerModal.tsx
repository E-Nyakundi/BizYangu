'use client'

import { useEffect, useState } from 'react'
import { listProductUnits } from '@/lib/catalog'
import { productUnitLabel } from '@/lib/knowledge'
import type { Product, ProductUnit } from '@/lib/types'
import { COPY } from '@/lib/copy'

export default function UnitPickerModal({
  product, onClose, onSelect,
}: {
  product: Product
  onClose: () => void
  onSelect: (unit: ProductUnit | null) => void
}) {
  const [units, setUnits] = useState<ProductUnit[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listProductUnits(product.id)
      .then(setUnits)
      .catch(() => setUnits([]))
      .finally(() => setLoading(false))
  }, [product.id])

  const sellable = units.filter((u) => u.is_sellable)

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
          padding: 'var(--sp-4)', width: '100%', maxWidth: 420, maxHeight: '70vh', overflowY: 'auto',
        }}
      >
        <h3 style={{ fontSize: 17, fontWeight: 700, marginBottom: 'var(--sp-3)' }}>{COPY.SELL_CHOOSE_FORM_TITLE}</h3>

        {loading ? (
          <p style={{ fontSize: 13, color: 'var(--color-muted)' }}>{COPY.LOADING}</p>
        ) : sellable.length <= 1 ? (
          <p style={{ fontSize: 13, color: 'var(--color-muted)' }}>{COPY.UNITS_EMPTY}</p>
        ) : (
          sellable.map((u) => {
            const outOfStock = Number(u.available_quantity) <= 0
            return (
              <button
                key={u.id}
                disabled={outOfStock}
                onClick={() => onSelect(u.is_root ? null : u)}
                style={{
                  width: '100%', textAlign: 'left', padding: '12px 14px', marginBottom: 8,
                  borderRadius: 12, border: '1px solid var(--surface-4)',
                  background: 'var(--surface-2)', opacity: outOfStock ? 0.45 : 1,
                  cursor: outOfStock ? 'not-allowed' : 'pointer',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>
                    {u.is_root ? product.name : productUnitLabel(u.unit)}
                  </span>
                  <span style={{ fontWeight: 700, color: 'var(--color-teal)', fontSize: 14 }}>
                    KES {Number(u.selling_price ?? product.selling_price).toLocaleString()}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 2 }}>
                  {outOfStock ? COPY.SELL_FORM_OUT_OF_STOCK : `${u.available_quantity} ${productUnitLabel(u.unit)}`}
                </div>
              </button>
            )
          })
        )}

        <button
          onClick={onClose}
          style={{ width: '100%', padding: '12px', borderRadius: 12, border: '1px solid var(--border)', background: 'transparent', marginTop: 4 }}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
