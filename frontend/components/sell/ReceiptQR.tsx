'use client'

/**
 * BizYangu — ReceiptQR
 *
 * Item D12 fix. The old ReceiptCard barcode was explicitly commented as
 * "decorative — not scannable, purely a receipt cue." This renders a
 * real QR code encoding the transaction's reference_number, which
 * resolves via GET /api/v1/transactions/receipt/{reference_number}/
 * (see lib/transactions.ts lookupReceipt).
 *
 * Deliberately encodes the bare reference_number, not a URL — there's no
 * public page for it to resolve to yet (see the pre-pilot doc's
 * Architecture Principles #3). Internally, staff can scan this straight
 * back into the app once a scanner screen exists, or just read/type the
 * printed reference_number under it in the meantime — the same value
 * either way, so nothing here needs to change when a scanner ships.
 *
 * Renders client-side via the `qrcode` package (no network call, no new
 * backend endpoint needed just to draw the code) as a data URL <img>,
 * which is what @capacitor/share + html2canvas (already used for
 * "Share receipt") can capture like any other image on the card.
 */

import { useEffect, useRef } from 'react'

export default function ReceiptQR({ value, size = 88 }: { value: string; size?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    let cancelled = false
    import('qrcode')
      .then((mod) => {
        if (cancelled || !canvasRef.current) return
        const toCanvas = (mod as any).toCanvas || (mod as any).default?.toCanvas
        if (!toCanvas) return
        return toCanvas(canvasRef.current, value, {
          width: size,
          margin: 0,
          color: {
            // Matches the receipt card's dark surface + teal-accent
            // vocabulary rather than a stark black-on-white QR.
            dark: '#e6fbf6',
            light: '#00000000',
          },
        })
      })
      .catch(() => {
        // Non-fatal — the printed reference_number below the code is
        // always there as a fallback if QR generation fails for any
        // reason (e.g. an unsupported webview or import interop quirk).
      })
    return () => { cancelled = true }
  }, [value, size])

  return (
    <canvas
      ref={canvasRef}
      width={size}
      height={size}
      style={{ display: 'block', margin: '0 auto' }}
      aria-label={value}
    />
  )
}
