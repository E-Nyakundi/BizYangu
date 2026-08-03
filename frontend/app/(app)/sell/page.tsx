'use client'

/**
 * BizYangu — SELL MODE
 * Product search → cart → payment method → confirm → success / receipt.
 * M-Pesa: STK Push via WebSocket + polling fallback + manual ref fallback.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuthStore } from '@/lib/auth'
import { listProducts } from '@/lib/catalog'
import { groupByCategory } from '@/lib/grouping'
import { createSale } from '@/lib/transactions'
import { initiateStkPush, pollStkStatus } from '@/lib/payments'
import { enqueue, queueLength, syncQueue } from '@/lib/offline-queue'
import { fetchBusiness } from '@/lib/business'
import { shareReceiptImage } from '@/lib/receipt-share'
import ReceiptCard from '@/components/sell/ReceiptCard'
import type { Product, CartItem, PaymentMethod, Transaction, MpesaWsEvent, Business } from '@/lib/types'
import { COPY } from '@/lib/copy'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'
const WS_BASE = API_BASE.replace(/^http/, 'ws').replace('/api/v1', '')

// Sentinel for the "no category set" chip — distinct from `null` (which
// means the "All" chip / no filter applied) since category_name itself
// can genuinely be null for a real product.
const UNCATEGORIZED = '__uncategorized__'

// ── WhatsApp receipt helper ───────────────────────────────────────────────────
// NOTE: This builds the customer-facing receipt message shared over WhatsApp.
// Its content (labels, "Asante...") is kept in Swahili intentionally — it's
// the branded document sent to shop customers, not app UI chrome.

function buildWhatsAppReceipt(txn: Transaction, businessName: string): string {
  const date = new Date(txn.created_at).toLocaleString('sw-KE', {
    dateStyle: 'short', timeStyle: 'short',
  })
  const lines = [
    `🧾 *RISITI — ${businessName}*`,
    `Nambari: *${txn.reference_number}*`,
    `Tarehe: ${date}`,
    ``,
    ...txn.items.map(
      (it) => `  • ${it.product_name} × ${Number(it.quantity)} @ KES ${Number(it.unit_price).toLocaleString()} = KES ${Number(it.subtotal).toLocaleString()}`
    ),
    ``,
    `*Jumla: KES ${Number(txn.total_amount).toLocaleString()}*`,
    `Malipo: ${txn.payment_method === 'MPESA' ? 'M-Pesa' : txn.payment_method === 'CASH' ? 'Taslimu' : txn.payment_method}`,
    txn.mpesa_reference ? `M-Pesa Ref: ${txn.mpesa_reference}` : '',
    ``,
    `Asante kwa biashara yako! 🙏`,
  ].filter((l) => l !== undefined)

  return `https://wa.me/?text=${encodeURIComponent(lines.join('\n'))}`
}

// ── Sub-components ────────────────────────────────────────────────────────────

function CategoryChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        flexShrink: 0,
        padding: 'var(--sp-1) var(--sp-3)',
        borderRadius: 'var(--radius-pill)',
        border: `1px solid ${active ? 'var(--color-teal)' : 'var(--surface-4)'}`,
        background: active ? 'rgba(0,229,196,0.1)' : 'var(--surface-2)',
        color: active ? 'var(--color-teal)' : 'var(--color-muted)',
        cursor: 'pointer', fontSize: 'var(--fs-xs)', fontFamily: 'var(--font-display)',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </button>
  )
}

function ProductCard({ product, onAdd }: { product: Product; onAdd: () => void }) {
  const outOfStock = product.track_stock && Number(product.current_stock) <= 0
  return (
    <button
      onClick={onAdd}
      disabled={outOfStock}
      style={{
        background: 'var(--surface-2)',
        border: '1px solid var(--surface-4)',
        borderRadius: 'var(--radius-card)',
        padding: 'var(--sp-3)',
        cursor: outOfStock ? 'not-allowed' : 'pointer',
        textAlign: 'left',
        width: '100%',
        opacity: outOfStock ? 0.45 : 1,
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={(e) => !outOfStock && ((e.currentTarget as HTMLElement).style.borderColor = 'var(--color-teal)')}
      onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.borderColor = 'var(--surface-4)')}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--sp-2)' }}>
        <span style={{ fontWeight: 600, fontSize: 'var(--fs-sm)', color: 'var(--color-off-white)', lineHeight: 1.3 }}>
          {product.name}
        </span>
        <span style={{ fontWeight: 700, color: 'var(--color-teal)', whiteSpace: 'nowrap', fontSize: 'var(--fs-sm)' }}>
          KES {Number(product.selling_price).toLocaleString()}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 'var(--sp-2)', marginTop: 'var(--sp-1)', alignItems: 'center' }}>
        <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
          {product.sku}
        </span>
        {product.track_stock && (
          <span className={`badge ${Number(product.current_stock) <= Number(product.low_stock_threshold) ? 'badge-error' : 'badge-muted'}`}
            style={{ fontSize: 'var(--fs-xs)' }}>
            {outOfStock ? COPY.SELL_OUT_OF_STOCK_BADGE : `${Number(product.current_stock)} ${product.unit}`}
          </span>
        )}
      </div>
    </button>
  )
}

function CustomItemForm({
  initialName,
  onAdd,
  onCancel,
}: {
  initialName: string
  onAdd: (name: string, price: number) => void
  onCancel: () => void
}) {
  const [name, setName] = useState(initialName)
  const [price, setPrice] = useState('')
  const nameRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    nameRef.current?.focus()
  }, [])

  const priceValue = Number(price)
  const canAdd = name.trim().length > 0 && price.trim().length > 0 && priceValue > 0

  function submit() {
    if (!canAdd) return
    onAdd(name.trim(), priceValue)
  }

  return (
    <div className="card" style={{ marginBottom: 'var(--sp-4)', padding: 'var(--sp-4)' }}>
      <h3 style={{ fontSize: 'var(--fs-sm)', fontWeight: 700, marginBottom: 'var(--sp-3)' }}>
        {COPY.SELL_CUSTOM_ITEM_TITLE}
      </h3>
      <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
        {COPY.SELL_CUSTOM_ITEM_NAME_LABEL}
      </label>
      <input
        ref={nameRef}
        className="input"
        type="text"
        placeholder={COPY.SELL_CUSTOM_ITEM_NAME_PLACEHOLDER}
        value={name}
        onChange={(e) => setName(e.target.value)}
        maxLength={200}
        style={{ width: '100%', marginBottom: 'var(--sp-3)' }}
      />
      <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
        {COPY.SELL_CUSTOM_ITEM_PRICE_LABEL}
      </label>
      <input
        className="input mono"
        type="number"
        inputMode="decimal"
        min="0"
        placeholder="0"
        value={price}
        onChange={(e) => setPrice(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        style={{ width: '100%', marginBottom: 'var(--sp-3)' }}
      />
      <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-3)' }}>
        {COPY.SELL_CUSTOM_ITEM_HINT}
      </p>
      <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
        <button className="btn-ghost" onClick={onCancel} style={{ flex: 1 }}>
          {COPY.SELL_CUSTOM_ITEM_CANCEL_BTN}
        </button>
        <button className="btn-primary" onClick={submit} disabled={!canAdd} style={{ flex: 1 }}>
          {COPY.SELL_CUSTOM_ITEM_ADD_BTN}
        </button>
      </div>
    </div>
  )
}

function CartRow({
  item,
  onInc,
  onDec,
  onRemove,
}: {
  item: CartItem
  onInc: () => void
  onDec: () => void
  onRemove: () => void
}) {
  const subtotal = item.quantity * Number(item.product.selling_price)
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 'var(--sp-3)',
      padding: 'var(--sp-3) 0', borderBottom: '1px solid var(--surface-3)',
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
          <span style={{ fontWeight: 600, fontSize: 'var(--fs-sm)' }}>{item.product.name}</span>
          {item.isCustom && (
            <span className="badge badge-muted" style={{ fontSize: 'var(--fs-xs)' }}>
              {COPY.SELL_CUSTOM_ITEM_BADGE}
            </span>
          )}
        </div>
        <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
          KES {Number(item.product.selling_price).toLocaleString()} × {item.quantity}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-1)' }}>
        <button className="btn-ghost" onClick={onDec}
          style={{ padding: '2px 10px', fontSize: '18px', lineHeight: 1 }}>−</button>
        <span className="mono" style={{ minWidth: 28, textAlign: 'center', fontWeight: 600 }}>{item.quantity}</span>
        <button className="btn-ghost" onClick={onInc}
          style={{ padding: '2px 10px', fontSize: '18px', lineHeight: 1 }}>+</button>
      </div>
      <div style={{ minWidth: 80, textAlign: 'right' }}>
        <div style={{ fontWeight: 700, color: 'var(--color-teal)', fontSize: 'var(--fs-sm)' }}>
          KES {subtotal.toLocaleString()}
        </div>
        <button className="btn-ghost btn-sm" onClick={onRemove} style={{
          color: 'var(--color-error)', marginTop: 2,
        }}>{COPY.SELL_REMOVE}</button>
      </div>
    </div>
  )
}

function SuccessScreen({
  transaction,
  business,
  businessName,
  onNewSale,
}: {
  transaction: Transaction
  business: Business | null
  businessName: string
  onNewSale: () => void
}) {
  const receiptRef = useRef<HTMLDivElement>(null)
  const [sharing, setSharing] = useState(false)
  const [shareError, setShareError] = useState('')

  async function handleShare() {
    if (!receiptRef.current || sharing) return
    setSharing(true)
    setShareError('')
    try {
      await shareReceiptImage(receiptRef.current, transaction, businessName)
    } catch {
      // Image capture/share failed outright — fall back to the plain
      // text WhatsApp link so the cashier still has a way to send it.
      setShareError(COPY.SELL_SHARE_IMAGE_FAIL)
    } finally {
      setSharing(false)
    }
  }

  return (
    <main style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--sp-5)' }}>
      <div style={{ maxWidth: 420, width: '100%' }}>
        <div style={{ textAlign: 'center', marginBottom: 'var(--sp-4)' }}>
          <div style={{
            width: 56, height: 56, borderRadius: '50%',
            background: 'rgba(0,229,196,0.15)', border: '2px solid var(--color-teal)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 28, marginBottom: 'var(--sp-3)',
          }}>✓</div>
          <h1 style={{ fontSize: 'var(--fs-lg)' }}>{COPY.SELL_SUCCESS_HEADING}</h1>
        </div>

        <div style={{ marginBottom: 'var(--sp-5)' }} ref={receiptRef}>
          <ReceiptCard transaction={transaction} business={business} businessNameFallback={businessName} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)' }}>
          <button
            className="btn-secondary"
            onClick={handleShare}
            disabled={sharing}
            style={{ textAlign: 'center', display: 'block', width: '100%' }}
          >
            {sharing ? COPY.SELL_SHARE_SENDING : COPY.SELL_SHARE_RECEIPT_BTN}
          </button>

          {shareError && (
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-error)', marginBottom: 'var(--sp-2)' }}>
                {shareError}
              </div>
              <a
                href={buildWhatsAppReceipt(transaction, businessName)}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-ghost"
                style={{ textAlign: 'center', display: 'block', fontSize: 'var(--fs-xs)' }}
              >
                {COPY.SELL_SHARE_TEXT_LINK}
              </a>
            </div>
          )}

          <button className="btn-primary" onClick={onNewSale}>
            {COPY.SELL_NEW_SALE_BTN}
          </button>
          <Link href="/sell/transactions" className="btn-ghost" style={{ textAlign: 'center', display: 'block', fontSize: 'var(--fs-xs)' }}>
            {COPY.SELL_VIEW_TRANSACTION}
          </Link>
        </div>
      </div>
    </main>
  )
}

// ── STK Waiting screen ────────────────────────────────────────────────────────

function StkWaitingScreen({
  phoneNumber,
  amount,
  onConfirmedWithRef,
  onCancel,
  pendingTxnId,
  checkoutRequestId,
}: {
  phoneNumber: string
  amount: number
  onConfirmedWithRef: (ref: string) => void
  onCancel: () => void
  pendingTxnId: string
  checkoutRequestId: string
}) {
  const [manualMode, setManualMode] = useState(false)
  const [manualRef, setManualRef] = useState('')
  const [pollError, setPollError] = useState('')
  const [dotCount, setDotCount] = useState(1)

  // Animate dots
  useEffect(() => {
    const t = setInterval(() => setDotCount((d) => (d % 3) + 1), 600)
    return () => clearInterval(t)
  }, [])

  // Polling fallback — every 5 seconds
  useEffect(() => {
    if (manualMode || !checkoutRequestId) return
    const interval = setInterval(async () => {
      try {
        const stk = await pollStkStatus(checkoutRequestId)
        if (stk.status === 'CONFIRMED') {
          onConfirmedWithRef(stk.mpesa_receipt_number ?? '')
        } else if (stk.status === 'FAILED' || stk.status === 'CANCELLED') {
          setPollError(COPY.SELL_STK_FAILED.replace('{reason}', stk.result_desc || COPY.SELL_STK_TRY_AGAIN))
          setManualMode(true)
        }
      } catch {
        // silent — WS is the primary path
      }
    }, 5000)
    return () => clearInterval(interval)
  }, [checkoutRequestId, manualMode, onConfirmedWithRef])

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 50,
      background: 'rgba(0,0,0,0.85)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 'var(--sp-5)',
    }}>
      <div className="card" style={{ maxWidth: 380, width: '100%', textAlign: 'center' }}>

        {!manualMode ? (
          <>
            {/* Spinner */}
            <div style={{ marginBottom: 'var(--sp-5)' }}>
              <div style={{
                width: 64, height: 64, borderRadius: '50%',
                border: '3px solid var(--surface-3)',
                borderTopColor: 'var(--color-teal)',
                margin: '0 auto',
                animation: 'byz-spin 1s linear infinite',
              }} />
            </div>

            <h2 style={{ fontSize: 'var(--fs-md)', marginBottom: 'var(--sp-2)' }}>
              {COPY.SELL_STK_WAITING_TITLE}{'.'.repeat(dotCount)}
            </h2>
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-1)' }}>
              {COPY.SELL_STK_SENT_TO}
            </p>
            <p className="mono" style={{ color: 'var(--color-teal)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-2)' }}>
              {phoneNumber}
            </p>
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)', marginBottom: 'var(--sp-5)' }}>
              {COPY.SELL_STK_ENTER_PIN}{' '}
              <strong style={{ color: 'var(--color-off-white)' }}>KES {amount.toLocaleString()}</strong>
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
              <button
                className="btn-ghost"
                style={{ fontSize: 'var(--fs-xs)' }}
                onClick={() => setManualMode(true)}
              >
                {COPY.SELL_STK_MANUAL_ENTRY}
              </button>
              <button
                className="btn-ghost"
                style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-error)' }}
                onClick={onCancel}
              >
                {COPY.SELL_STK_CANCEL}
              </button>
            </div>
          </>
        ) : (
          <>
            <div style={{ fontSize: 32, marginBottom: 'var(--sp-3)' }}>📱</div>
            <h2 style={{ fontSize: 'var(--fs-md)', marginBottom: 'var(--sp-2)' }}>
              {COPY.SELL_STK_MANUAL_TITLE}
            </h2>
            {pollError && (
              <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-xs)', marginBottom: 'var(--sp-3)' }}>
                {pollError}
              </p>
            )}
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-4)' }}>
              {COPY.SELL_STK_MANUAL_HELP}
            </p>
            <input
              className="input mono"
              type="text"
              placeholder="QFH3K2MRCE"
              value={manualRef}
              onChange={(e) => setManualRef(e.target.value.toUpperCase())}
              maxLength={20}
              style={{ width: '100%', letterSpacing: '0.05em', marginBottom: 'var(--sp-3)', textAlign: 'center' }}
              autoFocus
            />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
              <button
                className="btn-primary"
                disabled={manualRef.length < 6}
                onClick={() => onConfirmedWithRef(manualRef.trim())}
              >
                {COPY.SELL_STK_CONFIRM_CODE}
              </button>
              {!pollError && (
                <button
                  className="btn-ghost"
                  style={{ fontSize: 'var(--fs-xs)' }}
                  onClick={() => setManualMode(false)}
                >
                  {COPY.SELL_STK_BACK_TO_WAITING}
                </button>
              )}
              <button
                className="btn-ghost"
                style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-error)' }}
                onClick={onCancel}
              >
                {COPY.SELL_STK_CANCEL_SALE}
              </button>
            </div>
          </>
        )}
      </div>

      <style>{`
        @keyframes byz-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

// ── Main SELL MODE component ──────────────────────────────────────────────────

type View = 'pos' | 'stk_waiting' | 'success'

interface StkState {
  checkoutRequestId: string
  pendingTxnId: string
  phoneNumber: string
}

export default function SellPage() {
  const user = useAuthStore((s) => s.user)

  // Products
  const [products, setProducts] = useState<Product[]>([])
  const [loadingProducts, setLoadingProducts] = useState(true)
  const [search, setSearch] = useState('')
  // null = "All", UNCATEGORIZED sentinel = the no-category bucket,
  // anything else = an exact category_name to filter down to.
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  // Cart
  const [cart, setCart] = useState<CartItem[]>([])

  // Custom item (Phase 9, sell-without-inventory) — a not-in-catalog item
  // the cashier is about to add via a name + price
  const [customItemOpen, setCustomItemOpen] = useState(false)

  // Payment
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('CASH')
  const [mpesaPhone, setMpesaPhone] = useState('')
  const [mpesaRef, setMpesaRef] = useState('')
  const [notes, setNotes] = useState('')

  // Split-payment breakdown — only relevant when paymentMethod === 'MIXED'
  const [splitCash, setSplitCash] = useState('')
  const [splitMpesa, setSplitMpesa] = useState('')
  const [splitCredit, setSplitCredit] = useState('')

  // Credit-portion customer capture — required whenever paymentMethod is
  // 'CREDIT', or 'MIXED' with a non-zero splitCredit
  const [customerName, setCustomerName] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')

  // Submit state
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [completedTxn, setCompletedTxn] = useState<Transaction | null>(null)

  // STK
  const [stkState, setStkState] = useState<StkState | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Offline queue
  const [queuedCount, setQueuedCount] = useState(0)

  // View
  const [view, setView] = useState<View>('pos')

  // Mobile cart drawer (cart panel is a fixed sidebar on desktop; on
  // narrow screens it becomes a slide-up sheet toggled by a floating bar
  // so it never permanently covers the product grid — see .sell-cart-panel
  // media query below)
  const [mobileCartOpen, setMobileCartOpen] = useState(false)

  useEffect(() => {
    if (cart.length === 0) setMobileCartOpen(false)
  }, [cart.length])

  // Business details for the receipt header (address/phone) — best-effort,
  // receipt still renders fine without it via businessNameFallback
  const [business, setBusiness] = useState<Business | null>(null)

  // ── Load products ─────────────────────────────────────────────────────────

  useEffect(() => {
    listProducts()
      .then(setProducts)
      .catch(() => {})
      .finally(() => setLoadingProducts(false))
  }, [])

  useEffect(() => {
    fetchBusiness().then(setBusiness).catch(() => {})
  }, [])

  useEffect(() => {
    queueLength().then(setQueuedCount)
  }, [])

  useEffect(() => {
    if (typeof navigator !== 'undefined' && navigator.onLine) {
      syncQueue(createSale).then(({ synced }) => {
        if (synced > 0) setQueuedCount(0)
      })
    }
  }, [])

  // ── WebSocket connection (while STK waiting) ──────────────────────────────

  const handleWsMessage = useCallback((event: MessageEvent) => {
    try {
      const msg: MpesaWsEvent = JSON.parse(event.data)
      if (msg.type === 'stk_result') {
        if (msg.status === 'CONFIRMED') {
          // Close WS and move to success — we'll update the txn with the receipt
          wsRef.current?.close()
          handleStkConfirmed(msg.mpesa_receipt ?? '')
        } else if (msg.status === 'FAILED' || msg.status === 'CANCELLED') {
          // WS told us it failed — polling will surface the error message
          // Nothing to do here; the StkWaitingScreen polling will catch it
        }
      }
    } catch {
      // malformed message — ignore
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (view !== 'stk_waiting' || !user?.business_id) return

    const wsUrl = `${WS_BASE}/ws/mpesa/${user.business_id}/`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    ws.onmessage = handleWsMessage
    ws.onerror = () => {} // silent — polling is fallback

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [view, user?.business_id, handleWsMessage])

  // ── Filtered products ─────────────────────────────────────────────────────

  const activeProducts = products.filter((p) => p.is_active)
  const categoryGroups = groupByCategory(activeProducts)
  // Only show chips at all once there's something to actually filter by —
  // a business with everything in one bucket (or nothing categorized)
  // doesn't need a single "All" chip cluttering the screen.
  const showCategoryChips = categoryGroups.length > 1

  const filteredProducts = activeProducts.filter((p) => {
    if (categoryFilter === UNCATEGORIZED && p.category_name) return false
    if (categoryFilter && categoryFilter !== UNCATEGORIZED && p.category_name !== categoryFilter) return false
    return (
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.sku.toLowerCase().includes(search.toLowerCase())
    )
  })

  // ── Cart actions ──────────────────────────────────────────────────────────

  const addToCart = useCallback((product: Product) => {
    setCart((prev) => {
      const existing = prev.find((item) => item.product.id === product.id)
      if (existing) {
        const maxQty = product.track_stock ? Number(product.current_stock) : Infinity
        if (existing.quantity >= maxQty) return prev
        return prev.map((item) =>
          item.product.id === product.id ? { ...item, quantity: item.quantity + 1 } : item
        )
      }
      return [...prev, { product, quantity: 1 }]
    })
  }, [])

  // Adds a freeform "not in catalog" item (Phase 9, sell-without-inventory).
  // Built as a synthetic client-only Product so the rest of the cart UI
  // (CartRow, quantity +/-, total calc) works unchanged. track_stock: false
  // means quantity has no upper bound, matching a real non-tracked product.
  const addCustomToCart = useCallback((name: string, unitPrice: number) => {
    const now = new Date().toISOString()
    const syntheticProduct: Product = {
      id: `custom-${crypto.randomUUID()}`,
      name,
      sku: '',
      barcode: null,
      selling_price: String(unitPrice),
      cost_price: null,
      unit: 'piece',
      current_stock: '0',
      low_stock_threshold: '0',
      track_stock: false,
      image: null,
      is_active: true,
      category: null,
      category_name: null,
      stock_status: 'OK',
      created_at: now,
      updated_at: now,
    }
    setCart((prev) => [...prev, { product: syntheticProduct, quantity: 1, isCustom: true }])
    setCustomItemOpen(false)
  }, [])

  const removeFromCart = useCallback((productId: string) => {
    setCart((prev) => prev.filter((item) => item.product.id !== productId))
  }, [])

  const incrementQty = useCallback((productId: string) => {
    setCart((prev) =>
      prev.map((item) => {
        if (item.product.id !== productId) return item
        const maxQty = item.product.track_stock ? Number(item.product.current_stock) : Infinity
        return item.quantity < maxQty ? { ...item, quantity: item.quantity + 1 } : item
      })
    )
  }, [])

  const decrementQty = useCallback((productId: string) => {
    setCart((prev) =>
      prev.flatMap((item) => {
        if (item.product.id !== productId) return [item]
        if (item.quantity <= 1) return []
        return [{ ...item, quantity: item.quantity - 1 }]
      })
    )
  }, [])

  const total = cart.reduce((sum, item) => sum + item.quantity * Number(item.product.selling_price), 0)

  // ── Submit sale ───────────────────────────────────────────────────────────

  async function handleConfirmSale() {
    if (cart.length === 0) return

    // Client-side checks — the backend re-validates authoritatively, but
    // catching these here avoids a round-trip for the common mistakes.
    if (paymentMethod === 'CREDIT' && !customerName.trim()) {
      setSubmitError(COPY.SELL_CREDIT_CUSTOMER_REQUIRED)
      return
    }
    let mixedCash = 0, mixedMpesa = 0, mixedCredit = 0
    if (paymentMethod === 'MIXED') {
      mixedCash = parseFloat(splitCash) || 0
      mixedMpesa = parseFloat(splitMpesa) || 0
      mixedCredit = parseFloat(splitCredit) || 0
      if (Math.abs(mixedCash + mixedMpesa + mixedCredit - total) > 0.01) {
        setSubmitError(COPY.SELL_MIXED_AMOUNTS_MISMATCH.replace('{total}', total.toLocaleString()))
        return
      }
      if (mixedCredit > 0 && !customerName.trim()) {
        setSubmitError(COPY.SELL_CREDIT_CUSTOMER_REQUIRED)
        return
      }
    }

    setSubmitting(true)
    setSubmitError('')

    const needsCustomer = paymentMethod === 'CREDIT' || (paymentMethod === 'MIXED' && mixedCredit > 0)

    const payload = {
      items: cart.map((item) =>
        item.isCustom
          ? {
              name: item.product.name,
              unit_price: item.product.selling_price,
              quantity: String(item.quantity),
            }
          : {
              product_id: item.product.id,
              quantity: String(item.quantity),
            }
      ),
      payment_method: paymentMethod,
      mpesa_reference: paymentMethod === 'MPESA' ? '' : mpesaRef.trim(), // STK path sets ref later
      notes: notes.trim(),
      ...(paymentMethod === 'MIXED' && {
        cash_amount: String(mixedCash),
        mpesa_amount: String(mixedMpesa),
        credit_amount: String(mixedCredit),
      }),
      ...(needsCustomer && {
        customer_name: customerName.trim(),
        customer_phone: customerPhone.trim() || undefined,
      }),
    }

    try {
      if (paymentMethod === 'MPESA' && mpesaPhone.trim()) {
        // STK Push path: create the sale first (PENDING), then send STK
        const txn = await createSale(payload)
        const stk = await initiateStkPush({
          transaction_id: txn.id,
          phone_number: mpesaPhone.trim(),
        })
        setStkState({
          checkoutRequestId: stk.checkout_request_id,
          pendingTxnId: txn.id,
          phoneNumber: mpesaPhone.trim(),
        })
        setCompletedTxn(txn) // hold it; we'll show success once confirmed
        setView('stk_waiting')
      } else {
        // Cash / MIXED / CREDIT / manual M-Pesa ref
        const txn = await createSale(payload)
        setCompletedTxn(txn)
        setView('success')
        listProducts().then(setProducts).catch(() => {})
      }
    } catch (err: unknown) {
      const isOffline = !navigator.onLine || (err instanceof TypeError && err.message === 'Failed to fetch')
      if (isOffline) {
        await enqueue(payload)
        setQueuedCount((c) => c + 1)
        setSubmitError(COPY.SELL_OFFLINE_QUEUED)
      } else {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        setSubmitError(msg || COPY.SELL_GENERIC_ERROR)
      }
    } finally {
      setSubmitting(false)
    }
  }

  // Called by StkWaitingScreen when payment is confirmed (via WS or manual ref)
  function handleStkConfirmed(ref: string) {
    wsRef.current?.close()
    // Update txn object with the confirmed ref so receipt shows it
    if (completedTxn) {
      setCompletedTxn({ ...completedTxn, mpesa_reference: ref, payment_status: 'CONFIRMED' })
    }
    setStkState(null)
    setView('success')
    listProducts().then(setProducts).catch(() => {})
  }

  function handleStkCancel() {
    wsRef.current?.close()
    setStkState(null)
    setView('pos')
    setSubmitError(COPY.SELL_STK_REJECTED)
  }

  function handleNewSale() {
    setCart([])
    setPaymentMethod('CASH')
    setMpesaPhone('')
    setMpesaRef('')
    setNotes('')
    setSplitCash('')
    setSplitMpesa('')
    setSplitCredit('')
    setCustomerName('')
    setCustomerPhone('')
    setSubmitError('')
    setCompletedTxn(null)
    setStkState(null)
    setView('pos')
    setMobileCartOpen(false)
    setTimeout(() => searchRef.current?.focus(), 100)
  }

  // ── Render ────────────────────────────────────────────────────────────────

  if (view === 'success' && completedTxn) {
    return (
      <SuccessScreen
        transaction={completedTxn}
        business={business}
        businessName={user?.business_name || 'BizYangu'}
        onNewSale={handleNewSale}
      />
    )
  }

  return (
    <div data-main style={{ minHeight: '100dvh', display: 'flex', flexDirection: 'column', background: 'var(--surface-0)' }}>

      {/* STK Waiting overlay */}
      {view === 'stk_waiting' && stkState && (
        <StkWaitingScreen
          phoneNumber={stkState.phoneNumber}
          amount={total}
          checkoutRequestId={stkState.checkoutRequestId}
          pendingTxnId={stkState.pendingTxnId}
          onConfirmedWithRef={handleStkConfirmed}
          onCancel={handleStkCancel}
        />
      )}

      {/* ── Top bar ── */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: 'var(--sp-3) var(--sp-4)',
        borderBottom: '1px solid var(--surface-2)',
        background: 'var(--surface-1)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
          <Link href="/dashboard" className="btn-ghost" style={{ padding: 'var(--sp-1) var(--sp-2)', fontSize: 'var(--fs-xs)' }}>{COPY.SELL_GO_HOME}</Link>
          <span className="mono" style={{ color: 'var(--color-teal)', fontSize: 'var(--fs-xs)' }}>{COPY.SELL_MODE_LABEL}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
          {queuedCount > 0 && (
            <span className="badge badge-violet" style={{ fontSize: 'var(--fs-xs)' }}>
              {COPY.SELL_QUEUE_BADGE.replace('{count}', String(queuedCount))}
            </span>
          )}
          <Link href="/sell/transactions" className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }}>
            {COPY.SELL_TODAY_TRANSACTIONS}
          </Link>
        </div>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* ── Left: Product grid ── */}
        <div className="sell-products-scroll" style={{ flex: 1, overflowY: 'auto', padding: 'var(--sp-4)' }}>

          <input
            ref={searchRef}
            className="input"
            type="search"
            placeholder={COPY.SELL_SEARCH_FULL_PLACEHOLDER}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ marginBottom: 'var(--sp-3)', width: '100%' }}
            autoFocus
          />

          {showCategoryChips && (
            <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-3)', overflowX: 'auto', paddingBottom: 2 }}>
              <CategoryChip
                label={COPY.SELL_CATEGORY_ALL}
                active={categoryFilter === null}
                onClick={() => setCategoryFilter(null)}
              />
              {categoryGroups.map((g) => (
                <CategoryChip
                  key={g.categoryName ?? UNCATEGORIZED}
                  label={`${g.categoryName ?? COPY.SELL_CATEGORY_UNCATEGORIZED} (${g.items.length})`}
                  active={categoryFilter === (g.categoryName ?? UNCATEGORIZED)}
                  onClick={() => setCategoryFilter(g.categoryName ?? UNCATEGORIZED)}
                />
              ))}
            </div>
          )}

          {!customItemOpen && (
            <button
              className="btn-ghost"
              onClick={() => setCustomItemOpen(true)}
              style={{ fontSize: 'var(--fs-xs)', marginBottom: 'var(--sp-4)' }}
            >
              {COPY.SELL_ADD_CUSTOM_ITEM_BTN}
            </button>
          )}

          {customItemOpen && (
            <CustomItemForm
              initialName={search}
              onAdd={addCustomToCart}
              onCancel={() => setCustomItemOpen(false)}
            />
          )}

          {loadingProducts ? (
            <div style={{ color: 'var(--color-muted)', textAlign: 'center', padding: 'var(--sp-7)' }}>
              {COPY.SELL_LOADING_PRODUCTS}
            </div>
          ) : filteredProducts.length === 0 ? (
            <div style={{ color: 'var(--color-muted)', textAlign: 'center', padding: 'var(--sp-7)' }}>
              {search ? COPY.SELL_EMPTY_SEARCH.replace('{search}', search) : COPY.SELL_EMPTY_NONE}
              {search && !customItemOpen && (
                <div style={{ marginTop: 'var(--sp-3)' }}>
                  <button className="btn-secondary" onClick={() => setCustomItemOpen(true)}>
                    {COPY.SELL_SELL_ANYWAY_BTN.replace('{search}', search)}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 'var(--sp-3)' }}>
              {filteredProducts.map((p) => (
                <ProductCard key={p.id} product={p} onAdd={() => addToCart(p)} />
              ))}
            </div>
          )}
        </div>

        {/* ── Right: Cart + checkout ── */}
        <div
          className={`sell-cart-panel${mobileCartOpen ? ' cart-open' : ''}`}
          style={{
            width: 340,
            flexShrink: 0,
            borderLeft: '1px solid var(--surface-2)',
            display: 'flex',
            flexDirection: 'column',
            background: 'var(--surface-1)',
          }}
        >

          {/* Cart header */}
          <div style={{ padding: 'var(--sp-4)', borderBottom: '1px solid var(--surface-2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)' }}>
                <button
                  className="cart-close-btn"
                  onClick={() => setMobileCartOpen(false)}
                  aria-label={COPY.SELL_CLOSE_CART_LABEL}
                  style={{
                    display: 'none',
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: 'var(--color-off-white)', fontSize: 20, padding: 0, lineHeight: 1,
                  }}
                >
                  ←
                </button>
                <h2 style={{ fontSize: 'var(--fs-sm)', fontWeight: 700 }}>{COPY.SELL_CART}</h2>
              </div>
              {cart.length > 0 && (
                <button
                  onClick={() => setCart([])}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}
                >
                  {COPY.SELL_CLEAR_ALL}
                </button>
              )}
            </div>
          </div>

          {/* Cart items */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '0 var(--sp-4)' }}>
            {cart.length === 0 ? (
              <div style={{ padding: 'var(--sp-7) 0', textAlign: 'center', color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>
                {COPY.SELL_CART_EMPTY_HINT}
              </div>
            ) : (
              cart.map((item) => (
                <CartRow
                  key={item.product.id}
                  item={item}
                  onInc={() => incrementQty(item.product.id)}
                  onDec={() => decrementQty(item.product.id)}
                  onRemove={() => removeFromCart(item.product.id)}
                />
              ))
            )}
          </div>

          {/* Checkout panel */}
          {cart.length > 0 && (
            <div style={{ padding: 'var(--sp-4)', borderTop: '1px solid var(--surface-2)' }}>

              {/* Total */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 'var(--sp-4)' }}>
                <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>
                  {COPY.SELL_ITEMS_COUNT.replace('{count}', String(cart.reduce((n, i) => n + i.quantity, 0)))}
                </span>
                <span style={{ fontWeight: 700, fontSize: 'var(--fs-lg)', color: 'var(--color-teal)' }}>
                  KES {total.toLocaleString()}
                </span>
              </div>

              {/* Payment method */}
              <div style={{ marginBottom: 'var(--sp-3)' }}>
                <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                  {COPY.SELL_PAYMENT_METHOD}
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)' }}>
                  {(['CASH', 'MPESA', 'MIXED', 'CREDIT'] as PaymentMethod[]).map((method) => (
                    <button
                      key={method}
                      onClick={() => setPaymentMethod(method)}
                      style={{
                        padding: 'var(--sp-2)',
                        borderRadius: 'var(--radius-default)',
                        border: `1px solid ${paymentMethod === method ? 'var(--color-teal)' : 'var(--surface-4)'}`,
                        background: paymentMethod === method ? 'rgba(0,229,196,0.1)' : 'var(--surface-2)',
                        color: paymentMethod === method ? 'var(--color-teal)' : 'var(--color-muted)',
                        cursor: 'pointer',
                        fontWeight: paymentMethod === method ? 600 : 400,
                        fontSize: 'var(--fs-xs)',
                        fontFamily: 'var(--font-display)',
                        transition: 'all 0.15s',
                      }}
                    >
                      {method === 'CASH' ? COPY.SELL_PAYMENT_CASH_EMOJI : method === 'MPESA' ? COPY.SELL_PAYMENT_MPESA_EMOJI : method === 'MIXED' ? COPY.SELL_PAYMENT_MIXED_EMOJI : COPY.SELL_PAYMENT_CREDIT_EMOJI}
                    </button>
                  ))}
                </div>
              </div>

              {/* M-Pesa fields */}
              {paymentMethod === 'MPESA' && (
                <div style={{ marginBottom: 'var(--sp-3)' }}>
                  {/* Phone number for STK push */}
                  <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                    {COPY.SELL_STK_PHONE_LABEL}
                  </label>
                  <input
                    className="input mono"
                    type="tel"
                    placeholder="0712345678 or 254712345678"
                    value={mpesaPhone}
                    onChange={(e) => setMpesaPhone(e.target.value.trim())}
                    maxLength={15}
                    style={{ width: '100%', letterSpacing: '0.03em', marginBottom: 'var(--sp-2)' }}
                  />
                  <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
                    {COPY.SELL_STK_PHONE_HELP}
                  </p>
                  {/* Manual ref — shown when phone is empty */}
                  {!mpesaPhone.trim() && (
                    <>
                      <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                        {COPY.SELL_MPESA_REF_MANUAL}
                      </label>
                      <input
                        className="input mono"
                        type="text"
                        placeholder="QFH3K2MRCE"
                        value={mpesaRef}
                        onChange={(e) => setMpesaRef(e.target.value.toUpperCase())}
                        maxLength={20}
                        style={{ width: '100%', letterSpacing: '0.05em' }}
                      />
                    </>
                  )}
                </div>
              )}

              {/* MIXED payment — real split, not cosmetic (item D13) */}
              {paymentMethod === 'MIXED' && (
                <div style={{ marginBottom: 'var(--sp-3)' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--sp-2)', marginBottom: 'var(--sp-2)' }}>
                    <div>
                      <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                        {COPY.SELL_SPLIT_CASH_LABEL}
                      </label>
                      <input
                        className="input mono" type="number" inputMode="decimal" min="0" placeholder="0"
                        value={splitCash} onChange={(e) => setSplitCash(e.target.value)}
                        style={{ width: '100%' }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                        {COPY.SELL_SPLIT_MPESA_LABEL}
                      </label>
                      <input
                        className="input mono" type="number" inputMode="decimal" min="0" placeholder="0"
                        value={splitMpesa} onChange={(e) => setSplitMpesa(e.target.value)}
                        style={{ width: '100%' }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                        {COPY.SELL_SPLIT_CREDIT_LABEL}
                      </label>
                      <input
                        className="input mono" type="number" inputMode="decimal" min="0" placeholder="0"
                        value={splitCredit} onChange={(e) => setSplitCredit(e.target.value)}
                        style={{ width: '100%' }}
                      />
                    </div>
                  </div>
                  {(() => {
                    const remaining = total - ((parseFloat(splitCash) || 0) + (parseFloat(splitMpesa) || 0) + (parseFloat(splitCredit) || 0))
                    const rounded = Math.round(remaining * 100) / 100
                    if (rounded === 0) return null
                    const label = rounded > 0
                      ? COPY.SELL_SPLIT_REMAINING.replace('{amount}', rounded.toLocaleString())
                      : COPY.SELL_SPLIT_OVER.replace('{amount}', Math.abs(rounded).toLocaleString())
                    return (
                      <p style={{ fontSize: 'var(--fs-xs)', color: rounded > 0 ? 'var(--color-muted)' : 'var(--color-danger, #e5484d)', marginBottom: 'var(--sp-2)' }}>
                        {label}
                      </p>
                    )
                  })()}
                  {(parseFloat(splitMpesa) || 0) > 0 && (
                    <>
                      <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                        {COPY.SELL_MPESA_REF_OPTIONAL}
                      </label>
                      <input
                        className="input mono"
                        type="text"
                        placeholder="QFH3K2MRCE"
                        value={mpesaRef}
                        onChange={(e) => setMpesaRef(e.target.value.toUpperCase())}
                        maxLength={20}
                        style={{ width: '100%', letterSpacing: '0.05em', marginBottom: 'var(--sp-2)' }}
                      />
                    </>
                  )}
                  {(parseFloat(splitCredit) || 0) > 0 && (
                    <div style={{ paddingTop: 'var(--sp-2)', borderTop: '1px solid var(--surface-4)' }}>
                      <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                        {COPY.SELL_CREDIT_CUSTOMER_NAME_LABEL}
                      </label>
                      <input
                        className="input" type="text" placeholder={COPY.SELL_CREDIT_CUSTOMER_NAME_PLACEHOLDER}
                        value={customerName} onChange={(e) => setCustomerName(e.target.value)}
                        style={{ width: '100%', marginBottom: 'var(--sp-2)' }}
                      />
                      <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                        {COPY.SELL_CREDIT_CUSTOMER_PHONE_LABEL}
                      </label>
                      <input
                        className="input mono" type="tel" placeholder={COPY.SELL_CREDIT_CUSTOMER_PHONE_PLACEHOLDER}
                        value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value.trim())}
                        maxLength={15}
                        style={{ width: '100%' }}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* CREDIT payment — customer capture (item D16). This section
                  didn't exist at all before — a credit sale never asked
                  who owed the money, and never touched the Creditors list. */}
              {paymentMethod === 'CREDIT' && (
                <div style={{ marginBottom: 'var(--sp-3)' }}>
                  <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                    {COPY.SELL_CREDIT_CUSTOMER_NAME_LABEL}
                  </label>
                  <input
                    className="input" type="text" placeholder={COPY.SELL_CREDIT_CUSTOMER_NAME_PLACEHOLDER}
                    value={customerName} onChange={(e) => setCustomerName(e.target.value)}
                    style={{ width: '100%', marginBottom: 'var(--sp-2)' }}
                  />
                  <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                    {COPY.SELL_CREDIT_CUSTOMER_PHONE_LABEL}
                  </label>
                  <input
                    className="input mono" type="tel" placeholder={COPY.SELL_CREDIT_CUSTOMER_PHONE_PLACEHOLDER}
                    value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value.trim())}
                    maxLength={15}
                    style={{ width: '100%', marginBottom: 'var(--sp-1)' }}
                  />
                  <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                    {COPY.SELL_CREDIT_CUSTOMER_HELP}
                  </p>
                </div>
              )}

              {/* Notes */}
              <div style={{ marginBottom: 'var(--sp-3)' }}>
                <input
                  className="input"
                  type="text"
                  placeholder={COPY.SELL_NOTES_PLACEHOLDER}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  maxLength={200}
                  style={{ width: '100%' }}
                />
              </div>

              {/* Error */}
              {submitError && (
                <div style={{
                  background: 'rgba(255,77,109,0.1)', border: '1px solid var(--color-error)',
                  borderRadius: 'var(--radius-default)', padding: 'var(--sp-3)',
                  marginBottom: 'var(--sp-3)', fontSize: 'var(--fs-xs)', color: 'var(--color-error)',
                }}>
                  {submitError}
                </div>
              )}

              {/* CTA label changes for STK vs regular */}
              <button
                className="btn-primary"
                onClick={handleConfirmSale}
                disabled={submitting || cart.length === 0}
                style={{ width: '100%', padding: 'var(--sp-4)', fontSize: 'var(--fs-md)', fontWeight: 700 }}
              >
                {submitting
                  ? COPY.SELL_SUBMITTING
                  : paymentMethod === 'MPESA' && mpesaPhone.trim()
                    ? COPY.SELL_SEND_STK.replace('{amount}', total.toLocaleString())
                    : COPY.SELL_CONFIRM_AMOUNT.replace('{amount}', total.toLocaleString())
                }
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── Mobile floating cart bar (hidden on desktop; shown via media query) ── */}
      {cart.length > 0 && (
        <button
          className="sell-cart-bar"
          onClick={() => setMobileCartOpen(true)}
          style={{
            display: 'none',
            position: 'fixed',
            left: 'var(--sp-3)',
            right: 'var(--sp-3)',
            bottom: 'calc(64px + env(safe-area-inset-bottom) + var(--sp-3))',
            zIndex: 21,
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--color-teal)',
            color: 'var(--surface-0)',
            border: 'none',
            borderRadius: 'var(--radius-card)',
            padding: 'var(--sp-3) var(--sp-4)',
            cursor: 'pointer',
            fontFamily: 'var(--font-display)',
            fontWeight: 700,
            fontSize: 'var(--fs-sm)',
            boxShadow: '0 6px 20px rgba(0,0,0,0.45)',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
            <span style={{
              background: 'rgba(10,10,10,0.2)', borderRadius: '50%',
              minWidth: 22, height: 22, padding: '0 6px',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 'var(--fs-xs)',
            }}>
              {cart.reduce((n, i) => n + i.quantity, 0)}
            </span>
            {COPY.SELL_VIEW_CART}
          </span>
          <span>KES {total.toLocaleString()} →</span>
        </button>
      )}

      <style>{`
        @media (max-width: 767px) {
          .sell-products-scroll {
            padding-bottom: calc(64px + env(safe-area-inset-bottom) + 88px) !important;
          }
          .sell-cart-panel {
            position: fixed;
            inset: 0;
            z-index: 30;
            width: 100% !important;
            border-left: none !important;
            transform: translateY(100%);
            transition: transform 0.25s ease;
          }
          .sell-cart-panel.cart-open {
            transform: translateY(0);
          }
          .sell-cart-panel > div:last-child {
            padding-bottom: calc(env(safe-area-inset-bottom) + var(--sp-4)) !important;
          }
          .sell-cart-bar {
            display: flex !important;
          }
          .cart-close-btn {
            display: inline-flex !important;
          }
        }
      `}</style>
    </div>
  )
}
