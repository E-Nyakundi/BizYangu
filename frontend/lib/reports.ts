import { api } from './api'

export interface TopProduct {
  product_id: string
  name: string
  unit: string
  quantity_sold: string
  revenue: string
}

export interface StockAlertItem {
  product_id: string
  name: string
  current_stock: string
  low_stock_threshold: string
  unit: string
}

export interface StockAlert {
  low_stock_count: number
  out_of_stock_count: number
  items: StockAlertItem[]
}

export interface MoneySummary {
  gross_revenue: string
  refunded_amount: string
  net_revenue: string
  transaction_count: number
  average_transaction: string
  cash_total: string
  mpesa_total: string
  credit_total: string
  mixed_total: string
}

export interface DashboardReport extends MoneySummary {
  date: string
  revenue_change_pct: number | null
  yesterday_net_revenue: string
  top_products: TopProduct[]
  stock_alert: StockAlert
}

export interface LossByType {
  movement_type: 'LOSS' | 'DAMAGE'
  quantity_lost: string
  estimated_value: string
}

export interface LossByEmployee {
  user_id: string | null
  name: string
  quantity_lost: string
  estimated_value: string
}

export interface LossSummary {
  total_quantity_lost: string
  total_estimated_value: string
  by_product: {
    product_id: string
    name: string
    unit: string
    quantity_lost: string
    estimated_value: string
  }[]
  by_type: LossByType[]
  by_employee: LossByEmployee[]
}

export interface DailyReport extends MoneySummary {
  date: string
  voided_count: number
  top_products: TopProduct[]
  losses: LossSummary
}

export interface PeriodReport extends MoneySummary {
  start: string
  end: string
  daily_breakdown: { date: string; revenue: string; transaction_count: number }[]
  top_products: TopProduct[]
  losses: LossSummary
}

export interface ProductPerformanceRow {
  product_id: string
  name: string
  unit: string
  quantity_sold: string
  revenue: string
  cost_total: string | null
  margin: string | null
  margin_pct: number | null
}

export interface ProductPerformanceReport {
  start: string
  end: string
  products: ProductPerformanceRow[]
}

export interface LossReport extends LossSummary {
  start: string
  end: string
}

export interface EodSummary extends MoneySummary {
  date: string
  top_products: TopProduct[]
  stock_alert: StockAlert
  whatsapp_text: string
}

export async function getDashboard(): Promise<DashboardReport> {
  const { data } = await api.get('/reports/dashboard/')
  return data
}

export async function getDailyReport(date?: string): Promise<DailyReport> {
  const { data } = await api.get('/reports/daily/', { params: date ? { date } : {} })
  return data
}

export async function getPeriodReport(start?: string, end?: string): Promise<PeriodReport> {
  const { data } = await api.get('/reports/period/', { params: { start, end } })
  return data
}

export async function getProductPerformance(start?: string, end?: string): Promise<ProductPerformanceReport> {
  const { data } = await api.get('/reports/products/', { params: { start, end } })
  return data
}

export async function getLossReport(start?: string, end?: string): Promise<LossReport> {
  const { data } = await api.get('/reports/losses/', { params: { start, end } })
  return data
}

export async function getEodSummary(date?: string): Promise<EodSummary> {
  const { data } = await api.get('/reports/eod-summary/', { params: date ? { date } : {} })
  return data
}