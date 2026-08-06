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
