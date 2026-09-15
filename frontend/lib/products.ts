/**
 * BizYangu — shared product identity API calls (barcode resolve/candidate/verify).
 *
 * Separate from lib/catalog.ts on purpose: catalog.ts talks to
 * /catalog/products/, this business's own stock records. This file
 * talks to /products/, the cross-business shared barcode identity
 * layer — see backend apps/products/models.py for the full design
 * note on why those stay apart. A scan flow typically calls both: this
 * file to find out what the barcode *is*, catalog.ts's createProduct
 * to add it to *this business's* stock.
 */

import { api } from './api'

export type ResolutionState = 'FOUND_INTERNAL' | 'KNOWN_CANDIDATE' | 'UNRESOLVED'

export interface GlobalProduct {
  id: string
  barcode: string
  name: string
  brand: string
  category: string
  unit: string
  status: 'CANDIDATE' | 'VERIFIED' | 'DISPUTED'
  source: 'MANUAL' | 'WEB_SEARCH'
  confirmation_count: number
  conflict_count: number
}

export interface ResolveBarcodeResult {
  state: ResolutionState
  global_product: GlobalProduct | null
}

/** Internal-lookup-only in this slice — see backend view docstring. */
export async function resolveBarcode(barcode: string): Promise<ResolveBarcodeResult> {
  const { data } = await api.post('/products/resolve-barcode/', { barcode })
  return data
}

export interface CreateCandidatePayload {
  barcode: string
  name: string
  brand?: string
  category?: string
  unit?: string
}

/**
 * Called after resolveBarcode() returned UNRESOLVED and the user typed
 * in the product's own details. This only creates the shared-identity
 * record and records this business as its first confirming
 * contributor — it does NOT add the product to this business's own
 * stock. Call catalog.ts's createProduct alongside it for that.
 */
export async function createCandidate(payload: CreateCandidatePayload): Promise<GlobalProduct> {
  const { data } = await api.post('/products/candidates/', payload)
  return data
}

export interface VerifyGlobalProductPayload {
  matches_existing: boolean
  // Only read by the backend when matches_existing is false.
  name?: string
  brand?: string
  category?: string
  unit?: string
}

/** Confirms or disputes a KNOWN_CANDIDATE result from resolveBarcode(). */
export async function verifyGlobalProduct(
  barcode: string,
  payload: VerifyGlobalProductPayload
): Promise<GlobalProduct> {
  const { data } = await api.post(`/products/${encodeURIComponent(barcode)}/verify/`, payload)
  return data
}
