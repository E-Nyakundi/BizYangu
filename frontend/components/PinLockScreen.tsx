'use client'

/**
 * BizYangu — PIN lock screen.
 * Rendered by app/(app)/layout.tsx whenever this device has quick-PIN
 * entry turned on and the current app session hasn't unlocked yet.
 * On success it behaves exactly like a fresh OTP login (fresh cookies +
 * user profile) — the caller just needs to setUser() and mark the
 * session unlocked.
 */

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import PinPad from './PinPad'
import Logo from './Logo'
import Deepfield from './deepfield'
import { verifyPin, pinVerifyErrorInfo } from '@/lib/pin'
import { getLockDisplayName, setPinEnabledOnDevice, setSessionUnlocked } from '@/lib/device-lock'
import { isBiometricEnabled, unlockPinWithBiometric } from '@/lib/biometric'
import { COPY } from '@/lib/copy'
import type { UserProfile } from '@/lib/types'

interface PinLockScreenProps {
  onUnlocked: (user: UserProfile) => void
}

export default function PinLockScreen({ onUnlocked }: PinLockScreenProps) {
  const router = useRouter()
  const [pin, setPin] = useState('')
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lockedOut, setLockedOut] = useState(false)
  const [displayName, setDisplayName] = useState<string | null>(null)
  const [biometricReady, setBiometricReady] = useState(false)
  const triedBiometricOnMount = useRef(false)

  useEffect(() => {
    getLockDisplayName().then(setDisplayName)
    isBiometricEnabled().then((enabled) => {
      setBiometricReady(enabled)
      if (enabled && !triedBiometricOnMount.current) {
        triedBiometricOnMount.current = true
        tryBiometric()
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function tryBiometric() {
    const recoveredPin = await unlockPinWithBiometric()
    if (recoveredPin) {
      await submit(recoveredPin)
    }
  }

  async function submit(candidatePin: string) {
    setVerifying(true)
    setError(null)
    try {
      const { user } = await verifyPin(candidatePin)
      setSessionUnlocked(true)
      onUnlocked(user)
    } catch (err) {
      const info = pinVerifyErrorInfo(err)
      if (info.sessionDead) {
        // Refresh cookie is gone — no PIN will fix this. Drop back to a
        // real OTP login and stop pretending this device is unlockable.
        await setPinEnabledOnDevice(false)
        router.replace('/login')
        return
      }
      if (info.attemptsRemaining === 0) {
        setLockedOut(true)
      }
      setError(info.detail)
      setPin('')
    } finally {
      setVerifying(false)
    }
  }

  async function handleUseOtpInstead() {
    await setPinEnabledOnDevice(false)
    router.replace('/login')
  }

  return (
    <main className="grid-bg" style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--sp-5)' }}>
      <Deepfield position="fixed" zIndex={-1} opacity={0.4} />
      <div className="card" style={{ width: '100%', maxWidth: 380, textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 'var(--sp-3)' }}>
          <Logo height={36} />
        </div>
        <h1 style={{ fontSize: 'var(--fs-lg)', color: 'var(--color-off-white)', marginBottom: 'var(--sp-1)' }}>
          {COPY.PIN_LOCK_WELCOME_BACK}{displayName ? `, ${displayName}` : ''}
        </h1>
        <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-6)' }}>
          {lockedOut ? COPY.PIN_LOCK_LOCKED_TITLE : COPY.PIN_LOCK_ENTER_PIN}
        </p>

        {!lockedOut && (
          <PinPad
            value={pin}
            onChange={setPin}
            onComplete={submit}
            disabled={verifying}
            error={error}
            onBiometricPress={biometricReady ? tryBiometric : undefined}
          />
        )}

        <button
          type="button"
          className="btn-ghost"
          onClick={handleUseOtpInstead}
          style={{ marginTop: 'var(--sp-6)' }}
        >
          {COPY.PIN_LOCK_USE_OTP}
        </button>
      </div>
    </main>
  )
}
