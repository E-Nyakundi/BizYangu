'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { setupBusiness } from '@/lib/business'
import { listBusinessTypes } from '@/lib/knowledge'
import { apiErrorMessage } from '@/lib/auth'
import Deepfield from '@/components/deepfield'
import { COPY } from '@/lib/copy'
import type { BusinessTypeInfo } from '@/lib/types'

// Sentinel for "doesn't fit any of the real taxonomy types" — not part of
// knowledge/business_types.json, handled as a local fallback. Every real
// taxonomy type still goes through Business.type='CUSTOM' + custom_type_name
// on submit (see finishSetup below) since the legacy Type enum only covers
// 7 of the 9+ taxonomy types — custom_type_name is what actually renders,
// taxonomy_type_id is what Phase 4's product onboarding keys off of.
const OTHER_ID = '__OTHER__'

export default function SetupPage() {
  const router = useRouter()
  const [screen, setScreen] = useState(1)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  // Screen 1
  const [name, setName] = useState('')
  const [businessTypes, setBusinessTypes] = useState<BusinessTypeInfo[]>([])
  const [loadingTypes, setLoadingTypes] = useState(true)
  const [selectedId, setSelectedId] = useState<string>('')
  const [customTypeName, setCustomTypeName] = useState('')

  useEffect(() => {
    listBusinessTypes()
      .then((types) => {
        setBusinessTypes(types)
        // Default to the first real type rather than leaving nothing
        // selected — matches the old hardcoded list always defaulting
        // to DUKA, so screen 1 is submittable without a click if the
        // owner's business happens to be the first one shown.
        if (types.length > 0) setSelectedId(types[0].id)
      })
      .catch(() => {
        // Taxonomy fetch failed — fall back to "Other" only, so setup
        // is never fully blocked by this endpoint being unreachable.
        setSelectedId(OTHER_ID)
      })
      .finally(() => setLoadingTypes(false))
  }, [])

  const selectedType = businessTypes.find((t) => t.id === selectedId) ?? null

  // Screen 2
  const [paymentMode, setPaymentMode] = useState<'till' | 'paybill' | 'skip'>('till')
  const [tillNumber, setTillNumber] = useState('')
  const [paybillNumber, setPaybillNumber] = useState('')
  const [shortcode, setShortcode] = useState('')

  function goNextFromScreen1(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (selectedId === OTHER_ID && !customTypeName.trim()) {
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
        type: 'CUSTOM',
        custom_type_name: selectedId === OTHER_ID ? customTypeName.trim() : selectedType?.name,
        taxonomy_type_id: selectedId === OTHER_ID ? undefined : selectedId,
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
            {loadingTypes ? (
              <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-4)' }}>{COPY.STOCK_LOADING}</p>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
                {businessTypes.map((bt) => (
                  <button
                    key={bt.id}
                    type="button"
                    onClick={() => setSelectedId(bt.id)}
                    className={selectedId === bt.id ? 'btn-primary' : 'btn-secondary'}
                    style={{ justifyContent: 'center' }}
                  >
                    {bt.name}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setSelectedId(OTHER_ID)}
                  className={selectedId === OTHER_ID ? 'btn-primary' : 'btn-secondary'}
                  style={{ justifyContent: 'center' }}
                >
                  {COPY.SETUP_CATEGORY_CUSTOM}
                </button>
              </div>
            )}

            {selectedId === OTHER_ID && (
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
              <SummaryRow label={COPY.SETUP_SUMMARY_TYPE} value={selectedId === OTHER_ID ? customTypeName : selectedType?.name ?? ''} />
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
