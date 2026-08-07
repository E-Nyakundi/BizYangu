/**
 * BizYangu — catalog API calls (products, CSV import).
 */

import { api } from './api'
import type { Product, ProductUnit } from './types'

export interface ProductCreatePayload {
  name: string
  selling_price: string
  cost_price?: string
  current_stock?: string
  low_stock_threshold?: string
  unit?: string
  category?: string
  // Find-or-create by name — used by taxonomy-driven onboarding, which
  // only knows a taxonomy category's display name, never a pre-existing
  // Category id. Ignored if `category` (an id) is also given.
  category_name?: string
  // Phase 8 taxonomy tags — set alongside category/category_name (not
  // instead of) so the flat Category bucket still exists for display,
  // but the product also carries its real place in the taxonomy tree.
  // This is what powers the knowledge app's within-business suggestions
  // and stops every non-onboarding product from landing "uncategorized".
  taxonomy_category_id?: string
  taxonomy_subcategory_id?: string
  taxonomy_brand?: string
  // Phase 13 (Data Health) provenance tag. Reconciliation and CSV
  // import set this server-side instead — this is only for the two
  // paths that share this same create endpoint (taxonomy onboarding
  // and manual Add Product), where only the frontend knows which flow
  // is calling.
  created_via?: 'taxonomy' | 'manual'
}

export async function createProduct(payload: ProductCreatePayload): Promise<Product> {
  const { data } = await api.post('/catalog/products/', payload)
  return data
}

export async function listProducts(): Promise<Product[]> {
  const { data } = await api.get('/catalog/products/')
  return data
}

/** Single product, for the full-screen edit view. */
export async function fetchProduct(id: string): Promise<Product> {
  const { data } = await api.get(`/catalog/products/${id}/`)
  return data
}

// ── Full product-detail editing (owner/manager only) ────────────────────────
// Every field an owner/manager has authority over, post-onboarding.
// `current_stock` is deliberately absent — the backend drops it from a
// PATCH even if sent, since stock only changes through a movement-writing
// endpoint (Add Stock / Loss / Count) so the audit trail stays accurate.
export interface ProductUpdatePayload {
  name?: string
  barcode?: string
  selling_price?: string
  cost_price?: string | null
  unit?: string
  low_stock_threshold?: string
  track_stock?: boolean
  is_active?: boolean
  category?: string | null
  category_name?: string
  taxonomy_category_id?: string
  taxonomy_subcategory_id?: string
  taxonomy_brand?: string
  expiry_date?: string | null
}

/**
 * Updates any subset of a product's fields. Pass `image` separately —
 * when present, this sends multipart/form-data instead of JSON so the
 * file upload works; otherwise it's a plain JSON PATCH.
 */
export async function updateProduct(
  id: string,
  payload: ProductUpdatePayload,
  image?: File | null,
): Promise<Product> {
  if (image) {
    const formData = new FormData()
    Object.entries(payload).forEach(([key, value]) => {
      if (value === undefined) return
      // multipart has no native null — DRF's related/date fields already
      // treat an empty string as "clear this field" for form-encoded
      // data, so a null payload value (e.g. clearing category or
      // expiry_date) has to travel as '' here rather than being dropped,
      // or it would silently leave the existing value untouched instead
      // of clearing it whenever an image is attached to the same edit.
      formData.append(key, value === null ? '' : String(value))
    })
    formData.append('image', image)
    const { data } = await api.patch(`/catalog/products/${id}/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  }
  const { data } = await api.patch(`/catalog/products/${id}/`, payload)
  return data
}

/** Soft-deletes (hides from Sell/Stock, keeps history — reversible via reactivateProduct). */
export async function deactivateProduct(id: string): Promise<void> {
  await api.delete(`/catalog/products/${id}/`)
}

/** Undoes deactivateProduct. */
export async function reactivateProduct(id: string): Promise<Product> {
  const { data } = await api.patch(`/catalog/products/${id}/`, { is_active: true })
  return data
}

export interface CategoryOption {
  id: string
  name: string
}

/** Existing Category rows for this business — used to offer "pick an
 * existing category" alongside the taxonomy tree in Add Product flows. */
export async function listCategories(): Promise<CategoryOption[]> {
  const { data } = await api.get('/catalog/categories/')
  return data
}

export interface CSVImportResult {
  imported: number
  skipped: number
  errors: Array<{ row: number; error: string }>
}

export async function importProductsCsv(file: File): Promise<CSVImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/catalog/products/import/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

// ── Pack-to-unit selling / repackaging (C10) ────────────────────────────────

export interface ProductUnitPayload {
  unit: string
  parent?: string | null
  ratio_to_parent?: string | null
  is_repackaged?: boolean
  selling_price?: string | null
  is_sellable?: boolean
  is_root?: boolean
}

/** A product's full sellable-form tree (root + every child unit). */
export async function listProductUnits(productId: string): Promise<ProductUnit[]> {
  const { data } = await api.get(`/catalog/products/${productId}/units/`)
  return data
}

export async function createProductUnit(
  productId: string,
  payload: ProductUnitPayload,
): Promise<ProductUnit> {
  const { data } = await api.post(`/catalog/products/${productId}/units/`, payload)
  return data.unit
}

export async function updateProductUnit(
  productId: string,
  unitId: string,
  payload: Partial<ProductUnitPayload>,
): Promise<ProductUnit> {
  const { data } = await api.patch(`/catalog/products/${productId}/units/${unitId}/`, payload)
  return data.unit
}

export async function deleteProductUnit(productId: string, unitId: string): Promise<void> {
  await api.delete(`/catalog/products/${productId}/units/${unitId}/`)
}