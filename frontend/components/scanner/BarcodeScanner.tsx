'use client'

/**
 * BizYangu — BarcodeScanner
 *
 * Shared scanning surface. Deliberately generic: it decodes whatever's
 * in front of the camera (QR or 1D barcode) and hands the raw text back
 * via onDetected — it has no opinion about what that text means. That
 * interpretation belongs to the caller:
 *   - Transactions page: treats it as a receipt reference_number, feeds
 *     it into lookupReceipt().
 *   - Sell page: treats it as a product barcode, matches against the
 *     already-loaded product list.
 *   - Anywhere else scanning is useful later (Stock's Add Product
 *     barcode field, etc.) — same component, same pattern, no new
 *     scanning code needed, just a new onDetected handler.
 *
 * Runs via getUserMedia() + ZXing (@zxing/browser) rather than a native
 * Capacitor plugin, so it also works in a plain browser during `next
 * dev` — no native build needed to iterate on the UI. On Android this
 * needs the WebView permission grant in MainActivity.java (see comments
 * there) — NOT YET VERIFIED ON A REAL DEVICE. If the camera preview
 * never appears on an actual Android build, that's the first place to
 * check, not this file.
 */

import { useEffect, useRef, useState } from 'react'
import { COPY } from '@/lib/copy'

export default function BarcodeScanner({
  onDetected,
  onClose,
  title,
  hint,
}: {
  onDetected: (text: string) => void
  onClose: () => void
  title?: string
  hint?: string
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState('')
  const detectedRef = useRef(false)

  useEffect(() => {
    let cancelled = false
    let controls: { stop: () => void } | null = null

    import('@zxing/browser')
      .then(async ({ BrowserMultiFormatReader }) => {
        if (cancelled || !videoRef.current) return
        const reader = new BrowserMultiFormatReader()
        controls = await reader.decodeFromVideoDevice(
          undefined, // default camera — prefers rear camera on mobile automatically
          videoRef.current,
          (result) => {
            if (result && !detectedRef.current) {
              detectedRef.current = true
              onDetected(result.getText())
            }
          }
        )
      })
      .catch(() => {
        if (!cancelled) setError(COPY.SCANNER_CAMERA_ERROR)
      })

    return () => {
      cancelled = true
      controls?.stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 300,
        background: 'rgba(6,10,10,0.96)',
        display: 'flex', flexDirection: 'column',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 'var(--sp-4)' }}>
        <span style={{ color: 'var(--color-off-white)', fontWeight: 600, fontSize: 'var(--fs-sm)' }}>
          {title || COPY.SCANNER_TITLE}
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label={COPY.SCANNER_CLOSE}
          style={{ background: 'none', border: 'none', color: 'var(--color-off-white)', fontSize: 20, cursor: 'pointer', padding: 4 }}
        >
          ✕
        </button>
      </div>

      <div style={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
        <video
          ref={videoRef}
          muted
          playsInline
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
        <div
          aria-hidden
          style={{
            position: 'absolute', width: 220, height: 220,
            border: '2px solid var(--color-teal)', borderRadius: 16,
            boxShadow: '0 0 0 2000px rgba(6,10,10,0.5)',
            pointerEvents: 'none',
          }}
        />
      </div>

      <div style={{ padding: 'var(--sp-4)', textAlign: 'center' }}>
        {error ? (
          <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)' }}>{error}</p>
        ) : (
          <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{hint || COPY.SCANNER_HINT}</p>
        )}
      </div>
    </div>
  )
}
