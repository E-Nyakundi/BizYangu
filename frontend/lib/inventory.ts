/**
 * BizYangu — inventory API calls (STOCK MODE).
 */

import { api } from './api'

// ── Response types ────────────────────────────────────────────────────────────

export interface StockLevel {
  id: string
  name: string
  sku: string
  current_stock: string
  low_stock_threshold: string
  stock_status: 'OK' | 'LOW' | 'OUT'
  unit: string
  category_name: string | null
  track_stock: boolean
}

export interface StockMovement {
  id: string
  product: string
  product_name: string
  product_sku: string
  movement_type: 'SALE' | 'RESTOCK' | 'ADJUSTMENT' | 'LOSS' | 'DAMAGE' | 'REFUND' | 'COUNT'
  quantity_change: string
  quantity_before: string
  quantity_after: string
  notes: string
  created_by: string
  created_by_name: string
  created_at: string
}

export interface MovementListResult {
  count: number
  page: number
  page_size: number
  results: StockMovement[]
}

// ── API calls ─────────────────────────────────────────────────────────────────

export async function listStockLevels(params: { q?: string; category?: string } = {}): Promise<StockLevel[]> {
  const { data } = await api.get('/inventory/', { params })
  return data
}

export async function listLowStock(): Promise<StockLevel[]> {
  const { data } = await api.get('/inventory/low-stock/')
  return data
}

export async function listMovements(params: {
  product?: string
  type?: string
  page?: number
} = {}): Promise<MovementListResult> {
  const { data } = await api.get('/inventory/movements/', { params })
  return data
}

export interface StockCountPayload {
  product_id: string
  counted_quantity: string
  notes?: string
}

export async function submitStockCount(payload: StockCountPayload): Promise<{ detail: string; movement: StockMovement }> {
  const { data } = await api.post('/inventory/count/', payload)
  return data
}