'use client'

/**
 * BizYangu — invite acceptance page.
 * Reached via the link an owner generates in Settings → Staff → Invite
 * (POST /auth/invite/). Lives outside the (app) route group deliberately:
 * that layout auto-redirects anyone without a business_id to /setup,
 * which would hijack an invited cashier before they ever reach here.
 *
 * Flow:
 *   1. Not logged in  → mini phone/OTP form (same calls as /login), then
 *      redeem the invite immediately instead of routing to /setup.
 *   2. Logged in, no business yet → one confirm tap redeems the invite.
 *   3. Logged in, already has a business → blocked with an explanation
 *      (redeeming would silently move them between businesses otherwise).
 */

import { Suspense, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { requestOtp, verifyOtp, useAuthStore, apiErrorMessage } from '@/lib/auth'
import { acceptInvite } from '@/lib/business'
import Deepfield from '@/components/deepfield'
import { COPY } from '@/lib/copy'

type Step = 'loading' | 'phone' | 'otp' | 'confirm' | 'blocked' | 'success' | 'invalid'

export default function JoinPage() {
  return (
    <Suspense fallback={null}>
      <JoinPageInner />
    </Suspense>
  )
}

function JoinPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, isInitialized, isLoading, hydrate, setUser } = useAuthStore()

  const token = searchParams.get('token') ?? ''
  const roleParam = searchParams.get('role') // display only — DB record is authoritative
  const businessParam = searchParams.get('business') // display only, urlencoded

  const [step, setStep] = useState<Step>('loading')
  const [phone, setPhone] = useState('')
  const [otp, setOtp] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [resendIn, setResendIn] = useState(0)
  const resendTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!isInitialized) hydrate()
  }, [isInitialized, hydrate])

  useEffect(() => {
    if (!isInitialized || isLoading) return
    if (!token) {
      setStep('invalid')
    } else if (!user) {
      setStep('phone')
    } else if (user.business_id) {
      setStep('blocked')
    } else {
      setStep('confirm')
    }
  }, [isInitialized, isLoading, user, token])

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
    setIsSubmitting(true)
    try {
      await requestOtp(phone)
      setStep('otp')
      startResendCountdown()
    } catch (err) {
      setError(apiErrorMessage(err, COPY.ERRORS.OTP_SEND_ERROR))
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleVerifyOtp(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      const { user: verifiedUser } = await verifyOtp(phone, otp)
      setUser(verifiedUser)
      if (verifiedUser.business_id) {
        setStep('blocked')
        return
      }
      await redeemInvite()
    } catch (err) {
      setError(apiErrorMessage(err, COPY.ERRORS.INVALID_OTP))
    } finally {
      setIsSubmitting(false)
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

  async function redeemInvite() {
    setIsSubmitting(true)
    setError('')
    try {
      await acceptInvite(token)
      // Refresh the in-memory user so the (app) layout sees business_id set
      // and stops trying to bounce us to /setup.
      const { fetchMe } = await import('@/lib/auth')
      const refreshed = await fetchMe()
      setUser(refreshed)
      setStep('success')
      setTimeout(() => router.push('/dashboard'), 1200)
    } catch (err) {
      setError(apiErrorMessage(err, COPY.JOIN_INVALID))
      setStep('invalid')
    } finally {
      setIsSubmitting(false)
    }
  }

  const roleLabel = roleParam === 'MANAGER' ? COPY.SETTINGS_INVITE_MANAGER : COPY.SETTINGS_INVITE_CASHIER
  const businessName = businessParam ? decodeURIComponent(businessParam) : null

  return (
    <main className="grid-bg" style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--sp-5)' }}>
      <Deepfield position="fixed" zIndex={-1} opacity={0.4} />
      <div className="card" style={{ width: '100%', maxWidth: 380 }}>
        <div style={{ marginBottom: 'var(--sp-6)', textAlign: 'center' }}>
          <h1 style={{ fontSize: 'var(--fs-xl)', color: 'var(--color-teal)' }}>BizYangu</h1>
          <p style={{ color: 'var(--color-muted)', marginTop: 'var(--sp-2)' }}>{COPY.JOIN_TITLE}</p>
          {step !== 'invalid' && (
            <p style={{ color: 'var(--color-off-white)', marginTop: 'var(--sp-3)', fontSize: 'var(--fs-sm)' }}>
              {businessName
                ? COPY.JOIN_SUBTITLE_WITH_BUSINESS.replace('{business}', businessName)
                : COPY.JOIN_SUBTITLE_GENERIC}
            </p>
          )}
          {(step === 'phone' || step === 'otp' || step === 'confirm') && (
            <p className="mono" style={{ color: 'var(--color-teal)', marginTop: 'var(--sp-2)', fontSize: 'var(--fs-xs)' }}>
              {COPY.JOIN_ROLE_PREFIX}: {roleLabel}
            </p>
          )}
        </div>

        {step === 'loading' && (
          <p style={{ textAlign: 'center', color: 'var(--color-muted)' }}>{COPY.LOADING}</p>
        )}

        {step === 'invalid' && (
          <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', textAlign: 'center' }}>
            {token ? error || COPY.JOIN_INVALID : COPY.JOIN_INVALID_LINK}
          </p>
        )}

        {step === 'blocked' && (
          <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', textAlign: 'center' }}>
            {COPY.JOIN_ALREADY_HAS_BUSINESS}
          </p>
        )}

        {step === 'success' && (
          <p style={{ color: 'var(--color-teal)', fontSize: 'var(--fs-sm)', textAlign: 'center' }}>
            {COPY.JOIN_SUCCESS}
          </p>
        )}

        {step === 'confirm' && (
          <button
            className="btn-primary"
            disabled={isSubmitting}
            onClick={redeemInvite}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            {isSubmitting ? '…' : COPY.JOIN_TITLE}
          </button>
        )}

        {step === 'phone' && (
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
            <button type="submit" className="btn-primary" disabled={isSubmitting} style={{ width: '100%', justifyContent: 'center', marginTop: 'var(--sp-5)' }}>
              {isSubmitting ? COPY.LOGIN_LOADING_SEND : COPY.LOGIN_SEND_OTP}
            </button>
          </form>
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
            <button type="submit" className="btn-primary" disabled={isSubmitting || otp.length !== 6} style={{ width: '100%', justifyContent: 'center', marginTop: 'var(--sp-5)' }}>
              {isSubmitting ? COPY.LOGIN_LOADING_VERIFY : COPY.LOGIN_VERIFY}
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
