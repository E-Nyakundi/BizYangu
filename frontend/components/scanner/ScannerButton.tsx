'use client'

/**
 * BizYangu — ScannerButton
 * Drop-in trigger for BarcodeScanner. This is the "shared space" piece —
 * any screen that needs scanning imports this one component rather than
 * re-implementing the camera/modal/permission handling each time.
 */

import { useState } from 'react'
import BarcodeScanner from './BarcodeScanner'

export default function ScannerButton({
  onDetected,
  label,
  title,
  hint,
  className = 'btn-secondary',
}: {
  onDetected: (text: string) => void
  label?: string
  title?: string
  hint?: string
  className?: string
}) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        type="button"
        className={className}
        onClick={() => setOpen(true)}
        aria-label={label || 'Scan'}
      >
        📷{label ? ` ${label}` : ''}
      </button>
      {open && (
        <BarcodeScanner
          title={title}
          hint={hint}
          onClose={() => setOpen(false)}
          onDetected={(text) => {
            setOpen(false)
            onDetected(text)
          }}
        />
      )}
    </>
  )
}
