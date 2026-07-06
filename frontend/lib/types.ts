/**
 * BizYangu — shared frontend types matching backend serializers.
 */

export type UserRole = 'OWNER' | 'MANAGER' | 'CASHIER'

export interface UserProfile {
  id: string
  phone_number: string
  name: string
  role: UserRole
  business_id: string | null
  business_name: string | null
  subscription_status: string | null
  days_remaining: number | null
  demo_expires_at: string | null
  date_joined: string
}

export type BusinessType = 'DUKA' | 'HARDWARE' | 'BOUTIQUE' | 'STATIONERY' | 'CUSTOM'

export interface Business {
  id: string
  name: string
  type: BusinessType
  custom_type_name: string | null
  mpesa_till_number: string | null
  mpesa_paybill_number: string | null
  mpesa_business_shortcode: string | null
  address: string | null
  location_lat: number | null
  location_lng: number | null
  currency: string
  timezone: string
  owner_name: string
  owner_phone: string
  staff_count: number
  subscription_status: string
  days_remaining: number | null
  demo_expires_at: string | null
  created_at: string
  is_active: boolean
}

export interface StaffMember {
  id: string
  name: string
  phone_number: string
  role: UserRole
  date_joined: string
  is_active: boolean
}

export interface Product {
  id: string
  name: string
  sku: string
  barcode: string | null
  selling_price: string
  cost_price: string | null
  unit: string
  current_stock: string
  low_stock_threshold: string
  track_stock: boolean
  image: string | null
  is_active: boolean
  category: string | null
  category_name: string | null
  stock_status: string
  created_at: string
  updated_at: string
}

export type PaymentMethod = 'CASH' | 'MPESA' | 'CREDIT' | 'MIXED'
export type TransactionType = 'SALE' | 'STOCK_IN' | 'ADJUSTMENT' | 'LOSS' | 'DAMAGE' | 'REFUND' | 'TRANSFER'
export type PaymentStatus = 'PENDING' | 'CONFIRMED' | 'FAILED' | 'DISPUTED'

export interface TransactionItem {
  id: number
  product: string
  product_name: string
  product_sku: string
  quantity: string
  unit_price: string
  cost_price: string | null
  subtotal: string
  original_item: number | null
}

export interface Transaction {
  id: string
  type: TransactionType
  reference_number: string
  total_amount: string
  payment_method: PaymentMethod
  payment_status: PaymentStatus
  mpesa_reference: string
  notes: string
  created_by: string
  created_by_name: string
  created_at: string
  is_voided: boolean
  void_reason: string
  original_transaction: string | null
  refunded_amount: string | null
  items: TransactionItem[]
}

// ── Cart types (local state only) ──────────────────────────────────────────

export interface CartItem {
  product: Product
  quantity: number
}

// ── M-Pesa types ────────────────────────────────────────────────────────────

export type StkStatus = 'PENDING' | 'CONFIRMED' | 'FAILED' | 'CANCELLED'

export interface MPesaSTKRequest {
  id: string
  transaction: string
  checkout_request_id: string
  merchant_request_id: string
  phone_number: string
  amount: string
  status: StkStatus
  result_code: string | null
  result_desc: string | null
  created_at: string
  completed_at: string | null
  // Receipt from the M-Pesa callback; null until payment confirms.
  // Serializer reads this from transaction.mpesa_reference.
  mpesa_receipt_number: string | null
}

export type MpesaTxnType = 'C2B' | 'STK'

export interface MPesaTransaction {
  id: string
  transaction: string | null
  transaction_reference: string | null
  mpesa_receipt_number: string
  phone_number: string
  amount: string
  transaction_date: string
  transaction_type: MpesaTxnType
  is_matched: boolean
  is_reconciled: boolean
  created_at: string
}

// ── WebSocket message shape (mpesa_business_{id} group) ─────────────────────

export type MpesaWsEvent =
  | { type: 'stk_result'; checkout_request_id: string; status: StkStatus; transaction_id: string; mpesa_receipt: string | null }
  | { type: 'payment_received'; mpesa_transaction_id: string; amount: string; phone: string; is_matched: boolean }
