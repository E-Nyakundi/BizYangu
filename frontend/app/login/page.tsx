'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { requestOtp, verifyOtp, googleSignIn, useAuthStore, apiErrorMessage } from '@/lib/auth'
import { getGoogleSignIn } from '@/lib/google-auth'
import { goToApp } from '@/lib/post-login'
import Deepfield from '@/components/deepfield'
import Logo from '@/components/Logo'
import { COPY } from '@/lib/copy'

type Step = 'phone' | 'otp'

export default function LoginPage() {
  const router = useRouter()
  const setUser = useAuthStore((s) => s.setUser)

  const [step, setStep] = useState<Step>('phone')
  const [phone, setPhone] = useState('')
  const [otp, setOtp] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [resendIn, setResendIn] = useState(0)
  const resendTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  // Google sign-in — native shows its own button (calls handleGoogleClick
  // directly); web renders Google's own branded button into this ref once
  // Google Identity Services has loaded (see lib/google-auth.ts).
  const [isNativeGoogle, setIsNativeGoogle] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const webGoogleButtonRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const handle = await getGoogleSignIn()
      if (cancelled) return
      setIsNativeGoogle(handle.isNative)
      if (!handle.isNative && webGoogleButtonRef.current) {
        try {
          const idToken = await handle.mountWebButton(webGoogleButtonRef.current)
          if (!cancelled) await completeGoogleSignIn(idToken)
        } catch {
          // User hasn't interacted with the button yet, or GIS failed to
          // load — the button itself will just not render/respond;
          // nothing to surface until they actually try it.
        }
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function completeGoogleSignIn(idToken: string) {
    setError('')
    setGoogleLoading(true)
    try {
      const { user, is_new_user } = await googleSignIn(idToken)
      setUser(user)
      if (is_new_user || !user.business_id) {
        router.push('/setup')
      } else {
        await goToApp(router, user)
      }
    } catch (err) {
      setError(apiErrorMessage(err, COPY.ERRORS.GOOGLE_SIGNIN_ERROR))
    } finally {
      setGoogleLoading(false)
    }
  }

  async function handleNativeGoogleClick() {
    setError('')
    setGoogleLoading(true)
    try {
      const handle = await getGoogleSignIn()
      const idToken = await handle.signIn()
      await completeGoogleSignIn(idToken)
    } catch (err) {
      setError(apiErrorMessage(err, COPY.ERRORS.GOOGLE_SIGNIN_ERROR))
      setGoogleLoading(false)
    }
  }

  function startResendCountdown() {
    setResendIn(60)
    if (resendTimer.current) clearInterval(resendTimer.current)
    resendTimer.current = setInterval(() => {
      setResendIn((prev) => {
        if (prev <= 1) {
          if (resendTimer.current) clearInterval(resendTimer.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  async function handleRequestOtp(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    try {
      await requestOtp(phone)
      setStep('otp')
      startResendCountdown()
    } catch (err) {
      setError(apiErrorMessage(err, COPY.ERRORS.OTP_SEND_ERROR))
    } finally {
      setIsLoading(false)
    }
  }

  async function handleVerifyOtp(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    try {
      const { user, is_new_user } = await verifyOtp(phone, otp)
      setUser(user)
      if (is_new_user || !user.business_id) {
        router.push('/setup')
      } else {
        await goToApp(router, user)
      }
    } catch (err) {
      setError(apiErrorMessage(err, COPY.ERRORS.INVALID_OTP))
    } finally {
      setIsLoading(false)
    }
  }

  async function handleResend() {
    if (resendIn > 0) return
    setError('')
    try {
      await requestOtp(phone)
      startResendCountdown()
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  return (
    <main className="grid-bg" style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--sp-5)' }}>
      <Deepfield position="fixed" zIndex={-1} opacity={0.4} />
      <div className="card" style={{ width: '100%', maxWidth: 380 }}>
        <div style={{ marginBottom: 'var(--sp-6)', textAlign: 'center' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 'var(--sp-3)' }}>
            <Logo height={40} />
          </div>
          <h1 style={{ fontSize: 'var(--fs-xl)', color: 'var(--color-teal)' }}>BizYangu</h1>
          <p style={{ color: 'var(--color-muted)', marginTop: 'var(--sp-2)' }}>{COPY.LOGIN_TAGLINE}</p>
        </div>

        {step === 'phone' && (
          <>
            <div style={{ marginBottom: 'var(--sp-4)' }}>
              {isNativeGoogle ? (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleNativeGoogleClick}
                  disabled={googleLoading}
                  style={{ width: '100%', justifyContent: 'center' }}
                >
                  {googleLoading ? COPY.LOGIN_GOOGLE_LOADING : COPY.LOGIN_GOOGLE_BUTTON}
                </button>
              ) : (
                <div ref={webGoogleButtonRef} style={{ display: 'flex', justifyContent: 'center', minHeight: 44 }} />
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-3)', margin: 'var(--sp-4) 0', color: 'var(--color-muted)', fontSize: 'var(--fs-sm)' }}>
              <div style={{ flex: 1, height: 1, background: 'rgba(255, 255, 255, 0.08)' }} />
              {COPY.LOGIN_OR_DIVIDER}
              <div style={{ flex: 1, height: 1, background: 'rgba(255, 255, 255, 0.08)' }} />
            </div>
            <form onSubmit={handleRequestOtp}>
              <label htmlFor="phone" style={{ display: 'block', marginBottom: 'var(--sp-2)', fontSize: 'var(--fs-sm)' }}>
                {COPY.LOGIN_PHONE_LABEL}
              </label>
              <input
                id="phone"
                className="input"
                type="tel"
                inputMode="tel"
                placeholder={COPY.LOGIN_PHONE_PLACEHOLDER}
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                autoFocus
                required
              />
              {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', marginTop: 'var(--sp-3)' }}>{error}</p>}
              <button type="submit" className="btn-primary" disabled={isLoading} style={{ width: '100%', justifyContent: 'center', marginTop: 'var(--sp-5)' }}>
                {isLoading ? COPY.LOGIN_LOADING_SEND : COPY.LOGIN_SEND_OTP}
              </button>
            </form>
          </>
        )}

        {step === 'otp' && (
          <form onSubmit={handleVerifyOtp}>
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-4)' }}>
              {COPY.LOGIN_OTP_SENT_TO} <span className="mono" style={{ color: 'var(--color-off-white)' }}>{phone}</span>
            </p>
            <label htmlFor="otp" style={{ display: 'block', marginBottom: 'var(--sp-2)', fontSize: 'var(--fs-sm)' }}>
              {COPY.LOGIN_OTP_LABEL}
            </label>
            <input
              id="otp"
              className="input mono"
              type="text"
              inputMode="numeric"
              maxLength={6}
              placeholder={COPY.LOGIN_OTP_PLACEHOLDER}
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
              autoFocus
              required
              style={{ textAlign: 'center', fontSize: 'var(--fs-lg)', letterSpacing: '0.3em' }}
            />
            {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', marginTop: 'var(--sp-3)' }}>{error}</p>}
            <button type="submit" className="btn-primary" disabled={isLoading || otp.length !== 6} style={{ width: '100%', justifyContent: 'center', marginTop: 'var(--sp-5)' }}>
              {isLoading ? COPY.LOGIN_LOADING_VERIFY : COPY.LOGIN_VERIFY}
            </button>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 'var(--sp-4)' }}>
              <button type="button" className="btn-ghost" onClick={() => setStep('phone')}>
                {COPY.LOGIN_CHANGE_NUMBER}
              </button>
              <button type="button" className="btn-ghost" onClick={handleResend} disabled={resendIn > 0}>
                {resendIn > 0 ? COPY.LOGIN_RESEND_COUNTDOWN.replace('{seconds}', resendIn.toString()) : COPY.LOGIN_RESEND}
              </button>
            </div>
          </form>
        )}
      </div>
    </main>
  )
}
