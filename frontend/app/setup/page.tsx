'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { setupBusiness } from '@/lib/business'
import { apiErrorMessage } from '@/lib/auth'
import Deepfield from '@/components/deepfield'
import { COPY } from '@/lib/copy'
import type { BusinessType } from '@/lib/types'

const BUSINESS_TYPES: { value: BusinessType; label: string }[] = [
  { value: 'DUKA', label: COPY.SETUP_CATEGORY_DUKA },
  { value: 'HARDWARE', label: COPY.SETUP_CATEGORY_HARDWARE },
  { value: 'BOUTIQUE', label: COPY.SETUP_CATEGORY_BOUTIQUE },
  { value: 'STATIONERY', label: COPY.SETUP_CATEGORY_STATIONERY },
  { value: 'CUSTOM', label: COPY.SETUP_CATEGORY_CUSTOM },
]

export default function SetupPage() {
  const router = useRouter()
  const [screen, setScreen] = useState(1)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  // Screen 1
  const [name, setName] = useState('')
  const [type, setType] = useState<BusinessType>('DUKA')
  const [customTypeName, setCustomTypeName] = useState('')

  // Screen 2
  const [paymentMode, setPaymentMode] = useState<'till' | 'paybill' | 'skip'>('till')
  const [tillNumber, setTillNumber] = useState('')
  const [paybillNumber, setPaybillNumber] = useState('')
  const [shortcode, setShortcode] = useState('')

  function goNextFromScreen1(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (type === 'CUSTOM' && !customTypeName.trim()) {
      setError(COPY.ERRORS.BUSINESS_TYPE_REQUIRED)
      return
    }
    setScreen(2)
  }

  function goNextFromScreen2(e: React.FormEvent) {
    e.preventDefault()
    setScreen(3)
  }

  async function finishSetup() {
    setIsLoading(true)
    setError('')
    try {
      await setupBusiness({
        name: name.trim(),
        type,
        custom_type_name: type === 'CUSTOM' ? customTypeName.trim() : undefined,
        mpesa_till_number: paymentMode === 'till' ? tillNumber.trim() : undefined,
        mpesa_paybill_number: paymentMode === 'paybill' ? paybillNumber.trim() : undefined,
        mpesa_business_shortcode: paymentMode === 'paybill' ? shortcode.trim() : undefined,
      })
      router.push('/onboarding/products')
    } catch (err) {
      setError(apiErrorMessage(err, COPY.ERRORS.BUSINESS_SETUP_ERROR))
      setIsLoading(false)
    }
  }

  return (
    <main className="grid-bg" style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--sp-5)' }}>
      <Deepfield position="fixed" zIndex={-1} opacity={0.3} />
      <div className="card" style={{ width: '100%', maxWidth: 440 }}>
        <ProgressDots current={screen} total={3} />

        {screen === 1 && (
          <form onSubmit={goNextFromScreen1}>
            <h2 style={{ marginBottom: 'var(--sp-2)' }}>{COPY.SETUP_STEP1_TITLE}</h2>
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-5)' }}>
              {COPY.SETUP_STEP1_HELP}
            </p>

            <label style={{ display: 'block', marginBottom: 'var(--sp-2)', fontSize: 'var(--fs-sm)' }}>{COPY.SETUP_BUSINESS_NAME_LABEL}</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={COPY.SETUP_BUSINESS_NAME_PLACEHOLDER}
              required
              autoFocus
              style={{ marginBottom: 'var(--sp-5)' }}
            />

            <label style={{ display: 'block', marginBottom: 'var(--sp-2)', fontSize: 'var(--fs-sm)' }}>{COPY.SETUP_BUSINESS_TYPE_LABEL}</label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
              {BUSINESS_TYPES.map((bt) => (
                <button
                  key={bt.value}
                  type="button"
                  onClick={() => setType(bt.value)}
                  className={type === bt.value ? 'btn-primary' : 'btn-secondary'}
                  style={{ justifyContent: 'center' }}
                >
                  {bt.label}
                </button>
              ))}
            </div>

            {type === 'CUSTOM' && (
              <input
                className="input"
                value={customTypeName}
                onChange={(e) => setCustomTypeName(e.target.value)}
                placeholder={COPY.SETUP_BUSINESS_TYPE_CUSTOM}
                style={{ marginBottom: 'var(--sp-4)' }}
              />
            )}

            {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-3)' }}>{error}</p>}

            <button type="submit" className="btn-primary" style={{ width: '100%', justifyContent: 'center' }}>
              {COPY.SETUP_SUBMIT} →
            </button>
          </form>
        )}

        {screen === 2 && (
          <form onSubmit={goNextFromScreen2}>
            <h2 style={{ marginBottom: 'var(--sp-2)' }}>{COPY.SETUP_STEP2_TITLE}</h2>
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-5)' }}>
              {COPY.SETUP_STEP2_HELP}
            </p>

            <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
              <button type="button" className={paymentMode === 'till' ? 'btn-primary' : 'btn-secondary'} onClick={() => setPaymentMode('till')}>
                {COPY.SETUP_PAYMENT_TILL}
              </button>
              <button type="button" className={paymentMode === 'paybill' ? 'btn-primary' : 'btn-secondary'} onClick={() => setPaymentMode('paybill')}>
                {COPY.SETUP_PAYMENT_PAYBILL}
              </button>
              <button type="button" className={paymentMode === 'skip' ? 'btn-primary' : 'btn-secondary'} onClick={() => setPaymentMode('skip')}>
                {COPY.SETUP_PAYMENT_SKIP}
              </button>
            </div>

            {paymentMode === 'till' && (
              <input
                className="input"
                value={tillNumber}
                onChange={(e) => setTillNumber(e.target.value)}
                placeholder={COPY.SETUP_TILL_PLACEHOLDER}
                inputMode="numeric"
                style={{ marginBottom: 'var(--sp-4)' }}
              />
            )}

            {paymentMode === 'paybill' && (
              <>
                <input
                  className="input"
                  value={paybillNumber}
                  onChange={(e) => setPaybillNumber(e.target.value)}
                  placeholder={COPY.SETUP_PAYBILL_PLACEHOLDER}
                  inputMode="numeric"
                  style={{ marginBottom: 'var(--sp-3)' }}
                />
                <input
                  className="input"
                  value={shortcode}
                  onChange={(e) => setShortcode(e.target.value)}
                  placeholder={COPY.SETUP_SHORTCODE_PLACEHOLDER}
                  style={{ marginBottom: 'var(--sp-4)' }}
                />
              </>
            )}

            <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
              <button type="button" className="btn-ghost" onClick={() => setScreen(1)}>
                {COPY.SETUP_BACK}
              </button>
              <button type="submit" className="btn-primary" style={{ flex: 1, justifyContent: 'center' }}>
                {COPY.SETUP_CONTINUE}
              </button>
            </div>
          </form>
        )}

        {screen === 3 && (
          <div>
            <h2 style={{ marginBottom: 'var(--sp-2)' }}>{COPY.SETUP_STEP3_TITLE}</h2>
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-5)' }}>
              {COPY.SETUP_STEP3_HELP}
            </p>

            <div className="card-stat" style={{ marginBottom: 'var(--sp-5)' }}>
              <SummaryRow label={COPY.SETUP_SUMMARY_NAME} value={name} />
              <SummaryRow label={COPY.SETUP_SUMMARY_TYPE} value={type === 'CUSTOM' ? customTypeName : BUSINESS_TYPES.find((b) => b.value === type)?.label ?? ''} />
              <SummaryRow
                label={COPY.SETUP_SUMMARY_PAYMENT}
                value={
                  paymentMode === 'till' ? `Till ${tillNumber}` :
                  paymentMode === 'paybill' ? `Paybill ${paybillNumber}` :
                  COPY.SETUP_PAYMENT_NOT_SET
                }
              />
            </div>

            {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-3)' }}>{error}</p>}

            <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
              <button type="button" className="btn-ghost" onClick={() => setScreen(2)} disabled={isLoading}>
                {COPY.SETUP_BACK}
              </button>
              <button type="button" className="btn-primary" onClick={finishSetup} disabled={isLoading} style={{ flex: 1, justifyContent: 'center' }}>
                {isLoading ? COPY.SETUP_LOADING : COPY.SETUP_NEXT}
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}

function ProgressDots({ current, total }: { current: number; total: number }) {
  return (
    <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-6)' }}>
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          style={{
            height: 4,
            flex: 1,
            borderRadius: 'var(--radius-pill)',
            backgroundColor: i < current ? 'var(--color-teal)' : 'var(--surface-3)',
            transition: 'background-color 0.2s ease',
          }}
        />
      ))}
    </div>
  )
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--sp-2) 0' }}>
      <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)' }}>{label}</span>
      <span className="mono" style={{ fontSize: 'var(--fs-sm)' }}>{value}</span>
    </div>
  )
}
