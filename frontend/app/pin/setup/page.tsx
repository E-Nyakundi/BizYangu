'use client'

/**
 * BizYangu — PIN setup screen.
 * Shown right after a fresh OTP login when the user has no PIN yet
 * (see app/login/page.tsx), and reachable again from Settings to change
 * an existing PIN. Two steps: choose PIN → confirm PIN → (if biometric
 * hardware exists) offer to layer biometric unlock on top.
 */

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import PinPad from '@/components/PinPad'
import Deepfield from '@/components/deepfield'
import Logo from '@/components/Logo'
import { setPin } from '@/lib/pin'
import { setPinEnabledOnDevice } from '@/lib/device-lock'
import { isBiometricAvailable, enableBiometric } from '@/lib/biometric'
import { useAuthStore, apiErrorMessage } from '@/lib/auth'
import { COPY } from '@/lib/copy'

type Step = 'enter' | 'confirm' | 'biometric-offer' | 'saving'

const PIN_LENGTH = 4

export default function PinSetupPage() {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)

  const [step, setStep] = useState<Step>('enter')
  const [firstPin, setFirstPin] = useState('')
  const [pinInput, setPinInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  // Kept only long enough to hand off to enableBiometric() on the next
  // screen — never sent anywhere except the OS-encrypted credential
  // store (see lib/biometric.ts). Cleared as soon as that finishes.
  const [confirmedPin, setConfirmedPin] = useState('')

  function handleFirstEntry(pin: string) {
    setFirstPin(pin)
    setPinInput('')
    setStep('confirm')
  }

  async function handleConfirm(pin: string) {
    if (pin !== firstPin) {
      setError(COPY.PIN_SETUP_MISMATCH)
      setPinInput('')
      setFirstPin('')
      setStep('enter')
      return
    }

    setStep('saving')
    setError(null)
    try {
      await setPin(pin)
      if (user) {
        setUser({ ...user, has_pin: true })
      }
      await setPinEnabledOnDevice(true, user?.name || undefined)

      const hasBiometric = await isBiometricAvailable()
      if (hasBiometric) {
        setConfirmedPin(pin)
        setStep('biometric-offer')
      } else {
        router.replace('/dashboard')
      }
    } catch (err) {
      setError(apiErrorMessage(err))
      setPinInput('')
      setFirstPin('')
      setStep('enter')
    }
  }

  async function handleEnableBiometric() {
    if (confirmedPin) await enableBiometric(confirmedPin)
    setConfirmedPin('')
    router.replace('/dashboard')
  }

  function skipToDashboard() {
    setConfirmedPin('')
    router.replace('/dashboard')
  }

  return (
    <main className="grid-bg" style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--sp-5)' }}>
      <Deepfield position="fixed" zIndex={-1} opacity={0.4} />
      <div className="card" style={{ width: '100%', maxWidth: 380, textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 'var(--sp-3)' }}>
          <Logo height={36} />
        </div>

        {step === 'biometric-offer' ? (
          <>
            <h1 style={{ fontSize: 'var(--fs-lg)', color: 'var(--color-off-white)', marginBottom: 'var(--sp-2)' }}>
              {COPY.PIN_SETUP_ENABLE_BIOMETRIC_TITLE}
            </h1>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)', marginTop: 'var(--sp-6)' }}>
              <button
                type="button"
                className="btn-primary"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={handleEnableBiometric}
              >
                {COPY.PIN_SETUP_ENABLE_BIOMETRIC_YES}
              </button>
              <button type="button" className="btn-ghost" onClick={skipToDashboard}>
                {COPY.PIN_SETUP_ENABLE_BIOMETRIC_NO}
              </button>
            </div>
          </>
        ) : (
          <>
            <h1 style={{ fontSize: 'var(--fs-lg)', color: 'var(--color-off-white)', marginBottom: 'var(--sp-1)' }}>
              {COPY.PIN_SETUP_TITLE}
            </h1>
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-6)' }}>
              {step === 'confirm' ? COPY.PIN_SETUP_CONFIRM : COPY.PIN_SETUP_SUBTITLE}
            </p>

            <PinPad
              value={pinInput}
              onChange={setPinInput}
              onComplete={step === 'confirm' ? handleConfirm : handleFirstEntry}
              length={PIN_LENGTH}
              disabled={step === 'saving'}
              error={error}
            />

            <button type="button" className="btn-ghost" onClick={skipToDashboard} style={{ marginTop: 'var(--sp-6)' }}>
              {COPY.PIN_SETUP_SKIP}
            </button>
          </>
        )}
      </div>
    </main>
  )
}
