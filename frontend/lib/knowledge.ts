/**
 * BizYangu — knowledge base (Phase 8 taxonomy) API calls.
 * Read-only: onboarding's category picker, the reconciliation queue's
 * "pick from taxonomy" flow, and Stock's within-business suggestions.
 */

import { api } from './api'
import type { BusinessTypeInfo, Taxonomy, CategorySuggestions } from './types'

export async function listBusinessTypes(): Promise<BusinessTypeInfo[]> {
  const { data } = await api.get('/knowledge/business-types/')
  return data
}

/** Returns null (404) if no template exists yet for this business type. */
export async function fetchTaxonomy(businessTypeId: string): Promise<Taxonomy | null> {
  try {
    const { data } = await api.get(`/knowledge/taxonomy/${businessTypeId}/`)
    return data
  } catch {
    return null
  }
}

export async function fetchCategorySuggestions(categoryId: string): Promise<CategorySuggestions | null> {
  try {
    const { data } = await api.get(`/knowledge/suggestions/${categoryId}/`)
    return data
  } catch {
    return null
  }
}

/**
 * Product.unit's full choice list, id + display label, mirroring
 * knowledge/units.json and catalog migration 0004_expand_unit_vocabulary
 * exactly. Single source of truth for the frontend — the Add Product,
 * Resolve Unreconciled, and onboarding pickers all import this rather
 * than each keeping their own copy of the list.
 */
export const PRODUCT_UNITS: { id: string; label: string }[] = [
  { id: 'piece', label: 'Piece' },
  { id: 'kg', label: 'Kilogram' },
  { id: 'g', label: 'Gram' },
  { id: 'litre', label: 'Litre' },
  { id: 'ml', label: 'Millilitre' },
  { id: 'bottle', label: 'Bottle' },
  { id: 'crate', label: 'Crate' },
  { id: 'can', label: 'Can' },
  { id: 'packet', label: 'Packet' },
  { id: 'bag', label: 'Bag' },
  { id: 'bale', label: 'Bale' },
  { id: 'sack_50kg', label: '50kg sack' },
  { id: 'tonne', label: 'Tonne' },
  { id: 'gorogoro', label: 'Gorogoro (standard tin measure)' },
  { id: 'stick', label: 'Stick' },
  { id: 'dozen', label: 'Dozen' },
  { id: 'roll', label: 'Roll' },
  { id: 'metre', label: 'Metre' },
  { id: 'foot', label: 'Foot' },
  { id: 'pair', label: 'Pair' },
  { id: 'set', label: 'Set' },
  { id: 'bucket', label: 'Bucket' },
  { id: 'gauge', label: 'Gauge' },
  { id: 'service', label: 'Per service' },
  { id: 'session', label: 'Per session' },
]

const PRODUCT_UNIT_LABELS: Record<string, string> = Object.fromEntries(
  PRODUCT_UNITS.map((u) => [u.id, u.label])
)

/** Falls back to the raw id if it's somehow not in the list — never throws. */
export function productUnitLabel(unitId: string): string {
  return PRODUCT_UNIT_LABELS[unitId] ?? unitId
}

/**
 * Historically this mapped the taxonomy's ~25 unit ids down to
 * Product.unit's older, smaller 7-value set (see catalog migration
 * 0004_expand_unit_vocabulary for the reasoning). Product.unit now
 * uses the taxonomy's full vocabulary directly, so a taxonomy unit id
 * IS a valid Product.unit value — this is kept as a passthrough so
 * call sites (e.g. onboarding/products) don't need to change, and as
 * one place to reintroduce mapping if the two vocabularies ever
 * diverge again.
 */
export function taxonomyUnitToProductUnit(taxonomyUnitId: string): string {
  return taxonomyUnitId
}
