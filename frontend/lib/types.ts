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
  has_pin: boolean
}

export type BusinessType = 'DUKA' | 'HARDWARE' | 'BOUTIQUE' | 'STATIONERY' | 'CUSTOM'

export interface Business {
  id: string
  name: string
  type: BusinessType
  custom_type_name: string | null
  // Links to knowledge/business_types.json (Phase 8) — blank for
  // pre-Phase-8 businesses and for the "Other / doesn't fit" fallback
  // in setup, where there's deliberately no taxonomy match.
  taxonomy_type_id: string
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
  product: string | null
  product_name: string
  product_sku: string
  // Freeform name the cashier typed for an unreconciled (product=null) item.
  // Blank for normal catalog-backed items — use product_name for display.
  name: string
  // False when product is null — a sale-without-inventory item awaiting
  // reconciliation to a real catalog product.
  is_reconciled: boolean
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

// ── Knowledge base / taxonomy (Phase 8) ────────────────────────────────────
// Matches apps/knowledge/loader.py's public output shapes exactly —
// these are read-only, version-controlled JSON resolved server-side,
// never written to via the API.

export interface BusinessTypeInfo {
  id: string
  name: string
  kind: 'goods' | 'service' | 'mixed'
  niches: string[]
  sub_niche_capable: boolean
  combinable_with: string[]
}

export interface TaxonomyUnit {
  id: string
  label: string
  colloquial: string[]
}

export interface TaxonomyItem {
  name: string
  brands: string[]
  units: TaxonomyUnit[]
  stock_tracking: string
}

export interface TaxonomySubcategory {
  subcategory_id: string
  name: string
  items: TaxonomyItem[]
}

export interface TaxonomyCategory {
  category_id: string
  name: string
  // A category has either subcategories (which then hold items) or
  // items directly — never both, per loader.py's get_taxonomy().
  subcategories?: TaxonomySubcategory[]
  items?: TaxonomyItem[]
}

export interface Taxonomy {
  business_type_id: string
  kind: string
  categories: TaxonomyCategory[]
  // salon_barbershop-style service templates only — the physical goods
  // a service business also sells, kept separate from `categories` so
  // the frontend can render it as its own "you might also sell" section.
  retail_addon?: {
    category_id: string
    name: string
    items: TaxonomyItem[]
  }
}

export interface CategorySuggestions {
  category_id: string
  category_name: string
  business_item_count: number
  unlocked: boolean
  suggested_names: string[]
  suggested_brands: string[]
}

// ── Customer ledger (Phase 12) ─────────────────────────────────────────────
// Matches apps/customers/serializers.py's CustomerSerializer /
// CustomerPaymentSerializer, and the customer_detail view's extra
// sales/payments fields on top of the base Customer shape.

export interface Customer {
  id: string
  name: string
  phone: string
  notes: string
  balance: string
  oldest_unpaid_at: string | null
  created_at: string
  is_active: boolean
}

export interface CustomerPayment {
  id: string
  amount: string
  notes: string
  created_at: string
}

export interface CustomerDetail extends Customer {
  sales: Transaction[]
  payments: CustomerPayment[]
}

// ── Cart types (local state only) ──────────────────────────────────────────

export interface CartItem {
  product: Product
  quantity: number
  // True for a freeform "not in catalog" item (Phase 9, sell-without-
  // inventory). `product` is a client-only synthetic Product shape built
  // from the name/price the cashier typed — id is a locally-generated
  // `custom-...` string, never a real backend Product id. See
  // sell/page.tsx's addCustomToCart.
  isCustom?: boolean
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