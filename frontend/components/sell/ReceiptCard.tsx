'use client'

/**
 * BizYangu — ReceiptCard
 * A single, reusable "digital till slip" — used on the SELL MODE success
 * screen and (via the same component) anywhere else a past sale needs to
 * be re-shown, e.g. transaction history.
 *
 * Design language: LN Design System v5 tokens only (no new colors/fonts).
 * Paper-slip cues (perforated top/bottom edge, dashed section rules, a
 * decorative barcode derived from the reference number) rendered in the
 * app's existing dark surface + teal-accent + JetBrains Mono vocabulary,
 * rather than a literal white paper receipt — it should look like it
 * belongs in BizYangu, not like a scanned till slip.
 */

import type { Business, PaymentMethod, PaymentStatus, Transaction } from '@/lib/types'
import ReceiptQR from './ReceiptQR'

// ── Labels ───────────────────────────────────────────────────────────────────

const PAYMENT_METHOD_LABEL: Record<PaymentMethod, string> = {
  CASH: 'Taslimu',
  MPESA: 'M-Pesa',
  MIXED: 'Mchanganyiko',
  CREDIT: 'Mkopo',
}

const PAYMENT_STATUS: Record<PaymentStatus, { label: string; badge: string }> = {
  CONFIRMED: { label: 'Imelipwa', badge: 'badge-confirmed' },
  PENDING: { label: 'Inasubiri', badge: 'badge-pending' },
  FAILED: { label: 'Imeshindwa', badge: 'badge-failed' },
  DISPUTED: { label: 'Mgogoro', badge: 'badge-violet' },
}

// ── Component ────────────────────────────────────────────────────────────────

export default function ReceiptCard({
  transaction,
  business,
  businessNameFallback,
}: {
  transaction: Transaction
  business: Business | null
  businessNameFallback: string
}) {
  const businessName = business?.name || businessNameFallback
  const itemCount = transaction.items.reduce((n, it) => n + Number(it.quantity), 0)
  const status = PAYMENT_STATUS[transaction.payment_status]
  const dateStr = new Date(transaction.created_at).toLocaleString('sw-KE', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })

  return (
    <div
      className="receipt-card"
      style={{
        position: 'relative',
        maxWidth: 400,
        width: '100%',
        margin: '0 auto',
        background: 'var(--surface-2)',
        borderRadius: 'var(--radius-card)',
        padding: 'var(--sp-6) var(--sp-5) var(--sp-5)',
        boxShadow: '0 12px 32px rgba(0,0,0,0.35)',
        overflow: 'hidden',
      }}
    >
      {/* ── VOID stamp ── */}
      {transaction.is_voided && (
        <div
          style={{
            position: 'absolute',
            top: '38%',
            left: '50%',
            transform: 'translate(-50%, -50%) rotate(-14deg)',
            border: '3px solid var(--color-error)',
            color: 'var(--color-error)',
            borderRadius: 'var(--radius-subtle)',
            padding: '4px 18px',
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            fontSize: 'var(--fs-lg)',
            letterSpacing: '0.15em',
            opacity: 0.85,
            zIndex: 2,
            pointerEvents: 'none',
          }}
        >
          IMEFUTWA
        </div>
      )}

      {/* ── Payment status ribbon ── */}
      <div style={{ position: 'absolute', top: 'var(--sp-4)', right: 'var(--sp-4)' }}>
        <span className={`badge ${status.badge}`}>{status.label}</span>
      </div>

      {/* ── Business header ── */}
      <div style={{ textAlign: 'center', marginBottom: 'var(--sp-4)' }}>
        <div style={{ fontSize: 'var(--fs-lg)', fontWeight: 700, letterSpacing: '-0.02em' }}>
          {businessName}
        </div>
        {business?.address && (
          <div className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginTop: 4 }}>
            {business.address}
          </div>
        )}
        {business?.owner_phone && (
          <div className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginTop: 2 }}>
            {business.owner_phone}
          </div>
        )}
      </div>

      <div style={{ borderTop: '1px dashed var(--surface-4)', margin: 'var(--sp-4) 0' }} />

      {/* ── Meta ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 'var(--sp-1)' }}>
        <MetaRow label="Nambari" value={transaction.reference_number} accent />
        <MetaRow label="Tarehe" value={dateStr} />
        <MetaRow label="Mhudumu" value={transaction.created_by_name} />
      </div>

      <div style={{ borderTop: '1px dashed var(--surface-4)', margin: 'var(--sp-4) 0' }} />

      {/* ── Line items ── */}
      <div>
        {transaction.items.map((item) => (
          <div key={item.id} style={{ marginBottom: 'var(--sp-3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--sp-3)' }}>
              <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, lineHeight: 1.35 }}>
                {item.product_name}
              </span>
              <span className="mono" style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, whiteSpace: 'nowrap' }}>
                {Number(item.subtotal).toLocaleString()}
              </span>
            </div>
            <div className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
              {Number(item.quantity)} × {Number(item.unit_price).toLocaleString()}
            </div>
          </div>
        ))}
      </div>

      <div style={{ borderTop: '1px dashed var(--surface-4)', margin: 'var(--sp-4) 0' }} />

      {/* ── Total ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
          {itemCount} bidhaa
        </span>
        <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', letterSpacing: '0.1em' }}>
          JUMLA
        </span>
      </div>
      <div
        className="mono"
        style={{
          textAlign: 'right',
          fontSize: 'var(--fs-xl)',
          fontWeight: 700,
          color: 'var(--color-teal)',
          marginTop: 2,
        }}
      >
        KES {Number(transaction.total_amount).toLocaleString()}
      </div>

      <div style={{ borderTop: '1px dashed var(--surface-4)', margin: 'var(--sp-4) 0' }} />

      {/* ── Payment ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--sp-2)' }}>
        <span className="badge badge-muted">{PAYMENT_METHOD_LABEL[transaction.payment_method]}</span>
        {transaction.mpesa_reference && (
          <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
            Ref: {transaction.mpesa_reference}
          </span>
        )}
      </div>

      {transaction.void_reason && (
        <div
          style={{
            marginTop: 'var(--sp-3)',
            fontSize: 'var(--fs-xs)',
            color: 'var(--color-error)',
            background: 'rgba(255,77,109,0.08)',
            border: '1px solid var(--color-error)',
            borderRadius: 'var(--radius-default)',
            padding: 'var(--sp-2) var(--sp-3)',
          }}
        >
          Sababu ya kufuta: {transaction.void_reason}
        </div>
      )}

      {transaction.notes && (
        <div style={{ marginTop: 'var(--sp-3)', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', fontStyle: 'italic' }}>
          “{transaction.notes}”
        </div>
      )}

      {/* ── Footer ── */}
      <div style={{ textAlign: 'center', marginTop: 'var(--sp-6)' }}>
        <div style={{ fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-3)' }}>
          Asante kwa biashara yako 🙏
        </div>

        {/* real, scannable QR — item D12. Resolves via
            GET /transactions/receipt/{reference_number}/ */}
        <div style={{ marginBottom: 'var(--sp-2)' }}>
          <ReceiptQR value={transaction.reference_number} />
        </div>
        <div
          className="mono"
          style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', letterSpacing: '0.2em', marginTop: 'var(--sp-2)' }}
        >
          {transaction.reference_number}
        </div>
        <div className="mono" style={{ fontSize: 8, color: 'var(--surface-4)', marginTop: 'var(--sp-4)', letterSpacing: '0.15em' }}>
          BIZYANGU · POS
        </div>
      </div>

      {/* ── Perforated top/bottom edges ── */}
      <style>{`
        .receipt-card::before,
        .receipt-card::after {
          content: '';
          position: absolute;
          left: 0;
          right: 0;
          height: 12px;
          background-image: radial-gradient(circle at 10px 10px, var(--surface-0) 9px, transparent 9.5px);
          background-size: 20px 20px;
          background-repeat: repeat-x;
        }
        .receipt-card::before { top: -6px; background-position: 0 -4px; }
        .receipt-card::after  { bottom: -6px; background-position: 0 -10px; }
      `}</style>
    </div>
  )
}

function MetaRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--sp-3)' }}>
      <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{label}</span>
      <span
        className="mono"
        style={{
          fontSize: 'var(--fs-xs)',
          fontWeight: accent ? 700 : 400,
          color: accent ? 'var(--color-teal)' : 'var(--color-off-white)',
          letterSpacing: accent ? '0.05em' : 'normal',
        }}
      >
        {value}
      </span>
    </div>
  )
}
