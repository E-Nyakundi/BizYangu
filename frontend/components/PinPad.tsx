'use client'

/**
 * BizYangu — reusable numeric PIN pad.
 * Controlled by length only: fills left-to-right, fires onComplete once
 * `value.length === length`, caller resets `value` back to '' on error.
 */

import { useEffect } from 'react'

interface PinPadProps {
  value: string
  onChange: (next: string) => void
  onComplete: (pin: string) => void
  length?: number
  disabled?: boolean
  error?: string | null
  /** Show a fingerprint button that triggers a biometric retry. */
  onBiometricPress?: () => void
}

export default function PinPad({
  value,
  onChange,
  onComplete,
  length = 4,
  disabled = false,
  error = null,
  onBiometricPress,
}: PinPadProps) {
  useEffect(() => {
    if (value.length === length) {
      onComplete(value)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, length])

  function press(digit: string) {
    if (disabled || value.length >= length) return
    onChange(value + digit)
  }

  function backspace() {
    if (disabled) return
    onChange(value.slice(0, -1))
  }

  const digits = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--sp-5)' }}>
      {/* Dots */}
      <div style={{ display: 'flex', gap: 'var(--sp-3)' }}>
        {Array.from({ length }).map((_, i) => (
          <div
            key={i}
            style={{
              width: 16,
              height: 16,
              borderRadius: '50%',
              border: `1px solid ${error ? 'var(--color-error)' : 'var(--color-teal)'}`,
              background: i < value.length ? (error ? 'var(--color-error)' : 'var(--color-teal)') : 'transparent',
              transition: 'background 0.1s',
            }}
          />
        ))}
      </div>

      {error && (
        <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', textAlign: 'center', margin: 0 }}>
          {error}
        </p>
      )}

      {/* Keypad */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 64px)',
          gap: 'var(--sp-4)',
          justifyContent: 'center',
        }}
      >
        {digits.map((d) => (
          <button
            key={d}
            type="button"
            className="mono"
            disabled={disabled}
            onClick={() => press(d)}
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              border: '1px solid var(--surface-3)',
              background: 'var(--surface-2)',
              color: 'var(--color-off-white)',
              fontSize: 'var(--fs-lg)',
              cursor: disabled ? 'default' : 'pointer',
            }}
          >
            {d}
          </button>
        ))}

        {/* Bottom row: biometric | 0 | backspace */}
        <button
          type="button"
          onClick={onBiometricPress}
          disabled={disabled || !onBiometricPress}
          style={{
            width: 64,
            height: 64,
            borderRadius: '50%',
            border: 'none',
            background: 'transparent',
            color: onBiometricPress ? 'var(--color-teal)' : 'transparent',
            fontSize: 24,
            cursor: onBiometricPress && !disabled ? 'pointer' : 'default',
          }}
          aria-label="Fungua kwa alama ya kidole"
        >
          {onBiometricPress ? '⚬' : ''}
        </button>

        <button
          type="button"
          className="mono"
          disabled={disabled}
          onClick={() => press('0')}
          style={{
            width: 64,
            height: 64,
            borderRadius: '50%',
            border: '1px solid var(--surface-3)',
            background: 'var(--surface-2)',
            color: 'var(--color-off-white)',
            fontSize: 'var(--fs-lg)',
            cursor: disabled ? 'default' : 'pointer',
          }}
        >
          0
        </button>

        <button
          type="button"
          onClick={backspace}
          disabled={disabled || value.length === 0}
          style={{
            width: 64,
            height: 64,
            borderRadius: '50%',
            border: 'none',
            background: 'transparent',
            color: value.length ? 'var(--color-muted)' : 'transparent',
            fontSize: 20,
            cursor: disabled ? 'default' : 'pointer',
          }}
          aria-label="Futa"
        >
          ⌫
        </button>
      </div>
    </div>
  )
}
