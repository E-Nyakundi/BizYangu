'use client'

/**
 * BizYangu — full product-detail edit screen.
 * Build-plan item C8: "Full product-detail editing after onboarding as a
 * dedicated screen." Reached from the Stock drawer's "Edit details" link
 * (see /stock/page.tsx's ProductDrawer). Owner/manager only.
 *
 * A dedicated screen rather than a modal because the surface here (image,
 * barcode, price, cost, unit, category + taxonomy drill-down, expiry,
 * track-stock toggle, deactivate) is the same shape as onboarding's
 * per-product step, not a quick action — it deserves the room.
 *
 * Static export (next.config.js: output: 'export') means no dynamic
 * [id] route — the product id is a query param, same pattern as
 * app/join/page.tsx's invite token.
 *
 * current_stock is deliberately not editable here — see catalog.ts's
 * ProductUpdatePayload comment: stock only ever changes through a
 * movement-writing endpoint (Stock page's Add Stock / Loss / Count) so
 * the audit trail stays accurate. This screen links back to Stock for that.
 */

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useAuthStore } from '@/lib/auth'
import { apiErrorMessage } from '@/lib/api'
import {
  fetchProduct,
  updateProduct,
  deactivateProduct,
  reactivateProduct,
  listCategories,
  type CategoryOption,
} from '@/lib/catalog'
import { PRODUCT_UNITS, fetchTaxonomy } from '@/lib/knowledge'
import { fetchBusiness } from '@/lib/business'
import type { Product, Taxonomy } from '@/lib/types'
import { COPY } from '@/lib/copy'

export default function EditProductPage() {
  return (
    <Suspense fallback={<CenteredMessage text={COPY.EDIT_PRODUCT_LOADING} />}>
      <EditProductPageInner />
    </Suspense>
  )
}

function CenteredMessage({ text }: { text: string }) {
  return (
    <div style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <p className="mono" style={{ color: 'var(--color-muted)' }}>{text}</p>
    </div>
  )
}

function EditProductPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const productId = searchParams.get('id') ?? ''
  const user = useAuthStore((s) => s.user)
  const canWrite = user?.role === 'OWNER' || user?.role === 'MANAGER'

  const [product, setProduct] = useState<Product | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  // ── Form state ──────────────────────────────────────────────────────────
  const [name, setName] = useState('')
  const [barcode, setBarcode] = useState('')
  const [price, setPrice] = useState('')
  const [cost, setCost] = useState('')
  const [threshold, setThreshold] = useState('')
  const [unit, setUnit] = useState('piece')
  const [expiryDate, setExpiryDate] = useState('')
  const [trackStock, setTrackStock] = useState(true)
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)

  // Category picker — same encoding as AddProductModal on /stock:
  // '' (uncategorized), 'existing:<id>', 'taxonomy:<category_id>', 'new'
  const [existingCategories, setExistingCategories] = useState<CategoryOption[]>([])
  const [taxonomy, setTaxonomy] = useState<Taxonomy | null>(null)
  const [categoryKey, setCategoryKey] = useState('')
  const [newCategoryName, setNewCategoryName] = useState('')
  const [subcategoryId, setSubcategoryId] = useState('')

  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [savedToast, setSavedToast] = useState(false)
  const [deactivating, setDeactivating] = useState(false)

  useEffect(() => {
    if (!productId) { setLoadError(COPY.EDIT_PRODUCT_NOT_FOUND); setLoading(false); return }
    let cancelled = false
    setLoading(true)
    fetchProduct(productId)
      .then((p) => {
        if (cancelled) return
        setProduct(p)
        setName(p.name)
        setBarcode(p.barcode ?? '')
        setPrice(p.selling_price)
        setCost(p.cost_price ?? '')
        setThreshold(p.low_stock_threshold)
        setUnit(p.unit)
        setExpiryDate(p.expiry_date ?? '')
        setTrackStock(p.track_stock)
        setImagePreview(p.image)
        setCategoryKey(
          p.taxonomy_category_id ? `taxonomy:${p.taxonomy_category_id}`
            : p.category ? `existing:${p.category}`
            : ''
        )
        setSubcategoryId(p.taxonomy_subcategory_id ?? '')
      })
      .catch(() => { if (!cancelled) setLoadError(COPY.EDIT_PRODUCT_NOT_FOUND) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [productId])

  useEffect(() => {
    listCategories().then(setExistingCategories).catch(() => {/* non-critical */})
    fetchBusiness()
      .then((business) => business.taxonomy_type_id ? fetchTaxonomy(business.taxonomy_type_id) : null)
      .then(setTaxonomy)
      .catch(() => {/* non-critical — picker still works with existing categories only */})
  }, [])

  const selectedTaxonomyCategory = categoryKey.startsWith('taxonomy:')
    ? taxonomy?.categories.find((c) => c.category_id === categoryKey.slice('taxonomy:'.length))
    : undefined

  function handleImageChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setImageFile(file)
    setImagePreview(URL.createObjectURL(file))
  }

  async function handleSave() {
    if (!product) return
    if (!name.trim()) { setSaveError(COPY.EDIT_PRODUCT_NAME_ERROR); return }
    const sellingPrice = parseFloat(price)
    if (isNaN(sellingPrice) || sellingPrice <= 0) { setSaveError(COPY.EDIT_PRODUCT_PRICE_ERROR); return }

    setSaving(true); setSaveError('')

    const categoryFields =
      categoryKey === 'new'
        ? { category: null, category_name: newCategoryName.trim() || undefined }
        : categoryKey.startsWith('existing:')
        ? { category: categoryKey.slice('existing:'.length), taxonomy_category_id: '', taxonomy_subcategory_id: '' }
        : categoryKey.startsWith('taxonomy:')
        ? {
            category: null,
            category_name: selectedTaxonomyCategory?.name,
            taxonomy_category_id: selectedTaxonomyCategory?.category_id,
            taxonomy_subcategory_id: subcategoryId || '',
          }
        : { category: null, taxonomy_category_id: '', taxonomy_subcategory_id: '' }

    try {
      const updated = await updateProduct(
        product.id,
        {
          name: name.trim(),
          barcode: barcode.trim(),
          selling_price: price.trim(),
          cost_price: cost.trim() || null,
          unit,
          low_stock_threshold: threshold.trim() || undefined,
          track_stock: trackStock,
          expiry_date: expiryDate || null,
          ...categoryFields,
        },
        imageFile,
      )
      setProduct(updated)
      setImageFile(null)
      setSavedToast(true)
      setTimeout(() => setSavedToast(false), 1800)
    } catch (e: unknown) {
      setSaveError(apiErrorMessage(e, COPY.EDIT_PRODUCT_GENERIC_ERROR))
    } finally {
      setSaving(false)
    }
  }

  async function handleDeactivate() {
    if (!product) return
    if (!confirm(COPY.EDIT_PRODUCT_DEACTIVATE_CONFIRM.replace('{name}', product.name))) return
    setDeactivating(true)
    try {
      await deactivateProduct(product.id)
      router.push('/stock/')
    } catch (e: unknown) {
      setSaveError(apiErrorMessage(e, COPY.EDIT_PRODUCT_GENERIC_ERROR))
      setDeactivating(false)
    }
  }

  async function handleReactivate() {
    if (!product) return
    setDeactivating(true)
    try {
      const updated = await reactivateProduct(product.id)
      setProduct(updated)
    } catch (e: unknown) {
      setSaveError(apiErrorMessage(e, COPY.EDIT_PRODUCT_GENERIC_ERROR))
    } finally {
      setDeactivating(false)
    }
  }

  if (!canWrite) {
    return <CenteredMessage text={COPY.EDIT_PRODUCT_NOT_AUTHORIZED} />
  }

  if (loading) return <CenteredMessage text={COPY.EDIT_PRODUCT_LOADING} />
  if (loadError || !product) return <CenteredMessage text={loadError || COPY.EDIT_PRODUCT_NOT_FOUND} />

  return (
    <div style={{ minHeight: '100dvh', background: 'var(--surface-0)' }}>
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: 'var(--sp-3) var(--sp-4)',
        borderBottom: '1px solid var(--surface-2)',
        background: 'var(--surface-1)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <Link href="/stock" className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }}>{COPY.EDIT_PRODUCT_BACK}</Link>
        <span className="mono" style={{ color: 'var(--color-teal)', fontSize: 'var(--fs-xs)' }}>{COPY.EDIT_PRODUCT_TITLE}</span>
        <span style={{ width: 60 }} />
      </header>

      <main data-main style={{ maxWidth: 560, margin: '0 auto', padding: 'var(--sp-5) var(--sp-4)' }}>

        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', marginBottom: 'var(--sp-4)' }}>
          <h2 style={{ margin: 0, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {product.name}
          </h2>
          {!product.is_active && (
            <span className="badge badge-error" style={{ fontSize: 'var(--fs-xs)', flexShrink: 0 }}>
              {COPY.EDIT_PRODUCT_INACTIVE_BADGE}
            </span>
          )}
        </div>

        {/* Photo */}
        <Field label={COPY.EDIT_PRODUCT_IMAGE_LABEL}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
            <div style={{
              width: 64, height: 64, borderRadius: 'var(--radius-default)', overflow: 'hidden',
              background: 'var(--surface-2)', border: '1px solid var(--surface-3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              {imagePreview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={imagePreview} alt={product.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              ) : (
                <span style={{ color: 'var(--color-muted)', fontSize: 20 }}>📦</span>
              )}
            </div>
            <label className="btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
              {COPY.EDIT_PRODUCT_IMAGE_CHANGE}
              <input type="file" accept="image/*" onChange={handleImageChange} style={{ display: 'none' }} />
            </label>
            {imagePreview && (
              <button
                type="button"
                className="btn-ghost btn-sm"
                onClick={() => { setImageFile(null); setImagePreview(null) }}
              >
                {COPY.EDIT_PRODUCT_IMAGE_REMOVE}
              </button>
            )}
          </div>
        </Field>

        <Field label={COPY.EDIT_PRODUCT_NAME_LABEL}>
          <input className="input" type="text" value={name} onChange={(e) => setName(e.target.value)} style={{ width: '100%' }} />
        </Field>

        <Field label={COPY.EDIT_PRODUCT_BARCODE_LABEL}>
          <input className="input" type="text" placeholder={COPY.EDIT_PRODUCT_BARCODE_PLACEHOLDER}
            value={barcode} onChange={(e) => setBarcode(e.target.value)} style={{ width: '100%' }} />
        </Field>

        <Field label={COPY.EDIT_PRODUCT_CATEGORY_LABEL}>
          <select className="input" style={{ width: '100%' }} value={categoryKey}
            onChange={(e) => { setCategoryKey(e.target.value); setSubcategoryId('') }}>
            <option value="">{COPY.STOCK_NEW_CATEGORY_UNCATEGORIZED}</option>
            {existingCategories.length > 0 && (
              <optgroup label={COPY.STOCK_NEW_CATEGORY_EXISTING_GROUP}>
                {existingCategories.map((c) => (
                  <option key={c.id} value={`existing:${c.id}`}>{c.name}</option>
                ))}
              </optgroup>
            )}
            {taxonomy && taxonomy.categories.length > 0 && (
              <optgroup label={COPY.STOCK_NEW_CATEGORY_TAXONOMY_GROUP}>
                {taxonomy.categories.map((c) => (
                  <option key={c.category_id} value={`taxonomy:${c.category_id}`}>{c.name}</option>
                ))}
              </optgroup>
            )}
            <option value="new">{COPY.STOCK_NEW_CATEGORY_NEW_OPTION}</option>
          </select>
        </Field>

        {categoryKey === 'new' && (
          <Field label={COPY.STOCK_NEW_CATEGORY_NAME_LABEL}>
            <input className="input" type="text" placeholder={COPY.STOCK_NEW_CATEGORY_NAME_PLACEHOLDER}
              value={newCategoryName} onChange={(e) => setNewCategoryName(e.target.value)} style={{ width: '100%' }} />
          </Field>
        )}

        {selectedTaxonomyCategory?.subcategories && selectedTaxonomyCategory.subcategories.length > 0 && (
          <Field label={COPY.STOCK_NEW_CATEGORY_SUBCATEGORY_LABEL}>
            <select className="input" style={{ width: '100%' }} value={subcategoryId}
              onChange={(e) => setSubcategoryId(e.target.value)}>
              <option value="">{COPY.STOCK_NEW_CATEGORY_SUBCATEGORY_NONE}</option>
              {selectedTaxonomyCategory.subcategories.map((sub) => (
                <option key={sub.subcategory_id} value={sub.subcategory_id}>{sub.name}</option>
              ))}
            </select>
          </Field>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)' }}>
          <Field label={COPY.EDIT_PRODUCT_PRICE_LABEL}>
            <input className="input" type="number" min="0" step="any" inputMode="decimal"
              value={price} onChange={(e) => setPrice(e.target.value)} style={{ width: '100%' }} />
          </Field>
          <Field label={COPY.EDIT_PRODUCT_COST_LABEL}>
            <input className="input" type="number" min="0" step="any" inputMode="decimal"
              value={cost} onChange={(e) => setCost(e.target.value)} style={{ width: '100%' }} />
          </Field>
        </div>

        <Field label={COPY.EDIT_PRODUCT_THRESHOLD_LABEL}>
          <input className="input" type="number" min="0" step="any" inputMode="decimal"
            value={threshold} onChange={(e) => setThreshold(e.target.value)} style={{ width: '100%' }} />
        </Field>

        <Field label={COPY.EDIT_PRODUCT_UNIT_LABEL}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-2)', maxHeight: 140, overflowY: 'auto' }}>
            {PRODUCT_UNITS.map((u) => (
              <button key={u.id} type="button" onClick={() => setUnit(u.id)}
                style={{
                  padding: 'var(--sp-1) var(--sp-3)',
                  borderRadius: 'var(--radius-pill)',
                  border: `1px solid ${unit === u.id ? 'var(--color-teal)' : 'var(--surface-4)'}`,
                  background: unit === u.id ? 'rgba(0,229,196,0.1)' : 'var(--surface-2)',
                  color: unit === u.id ? 'var(--color-teal)' : 'var(--color-muted)',
                  cursor: 'pointer', fontSize: 'var(--fs-xs)', fontFamily: 'var(--font-display)',
                }}>
                {u.label}
              </button>
            ))}
          </div>
        </Field>

        <Field label={COPY.EDIT_PRODUCT_EXPIRY_LABEL}>
          <div style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center' }}>
            <input className="input" type="date" value={expiryDate}
              onChange={(e) => setExpiryDate(e.target.value)} style={{ flex: 1 }} />
            {expiryDate && (
              <button type="button" className="btn-ghost btn-sm" onClick={() => setExpiryDate('')}>
                {COPY.EDIT_PRODUCT_EXPIRY_CLEAR}
              </button>
            )}
          </div>
        </Field>

        <div style={{ marginBottom: 'var(--sp-4)' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', cursor: 'pointer' }}>
            <input type="checkbox" checked={trackStock} onChange={(e) => setTrackStock(e.target.checked)} />
            <span style={{ fontSize: 'var(--fs-sm)' }}>{COPY.EDIT_PRODUCT_TRACK_STOCK_LABEL}</span>
          </label>
          <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginTop: 4, marginLeft: 24 }}>
            {COPY.EDIT_PRODUCT_TRACK_STOCK_HELP}
          </p>
        </div>

        <Link href="/repackage" className="btn-secondary btn-sm" style={{ display: 'block', textAlign: 'center', marginBottom: 'var(--sp-4)' }}>
          {COPY.EDIT_PRODUCT_MANAGE_UNITS_LINK}
        </Link>

        {savedToast && (
          <div style={{
            background: 'rgba(0,229,196,0.1)', border: '1px solid var(--color-teal)',
            borderRadius: 'var(--radius-default)', padding: 'var(--sp-3)',
            marginBottom: 'var(--sp-3)', fontSize: 'var(--fs-xs)', color: 'var(--color-teal)',
          }}>
            {COPY.EDIT_PRODUCT_SAVED_TOAST}
          </div>
        )}
        {saveError && (
          <div style={{
            background: 'rgba(255,77,109,0.1)', border: '1px solid var(--color-error)',
            borderRadius: 'var(--radius-default)', padding: 'var(--sp-3)',
            marginBottom: 'var(--sp-3)', fontSize: 'var(--fs-xs)', color: 'var(--color-error)',
          }}>
            {saveError}
          </div>
        )}

        <button className="btn-primary" onClick={handleSave} disabled={saving} style={{ width: '100%', marginBottom: 'var(--sp-5)' }}>
          {saving ? COPY.EDIT_PRODUCT_SAVING : COPY.EDIT_PRODUCT_SAVE}
        </button>

        {/* Deactivate / reactivate — kept visually separate from the save
            action since it's a different kind of change (visibility, not
            a field edit) and destructive-ish (though reversible). */}
        <div style={{ borderTop: '1px solid var(--surface-2)', paddingTop: 'var(--sp-4)' }}>
          {product.is_active ? (
            <>
              <button className="btn-destructive btn-sm" onClick={handleDeactivate} disabled={deactivating} style={{ width: '100%' }}>
                {COPY.EDIT_PRODUCT_DEACTIVATE}
              </button>
              <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginTop: 'var(--sp-2)', textAlign: 'center' }}>
                {COPY.EDIT_PRODUCT_DEACTIVATE_HELP}
              </p>
            </>
          ) : (
            <button className="btn-secondary btn-sm" onClick={handleReactivate} disabled={deactivating} style={{ width: '100%' }}>
              {COPY.EDIT_PRODUCT_REACTIVATE}
            </button>
          )}
        </div>
      </main>
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
