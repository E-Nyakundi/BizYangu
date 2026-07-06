/**
 * BizYangu — catalog API calls (products, CSV import).
 */

import { api } from './api'
import type { Product } from './types'

export interface ProductCreatePayload {
  name: string
  selling_price: string
  cost_price?: string
  current_stock?: string
  low_stock_threshold?: string
  unit?: string
}

export async function createProduct(payload: ProductCreatePayload): Promise<Product> {
  const { data } = await api.post('/catalog/products/', payload)
  return data
}

export async function listProducts(): Promise<Product[]> {
  const { data } = await api.get('/catalog/products/')
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
