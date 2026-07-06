'use client'

import { useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createProduct, importProductsCsv } from '@/lib/catalog'
import { apiErrorMessage } from '@/lib/auth'
import Deepfield from '@/components/deepfield'
import { COPY } from '@/lib/copy'

interface DraftProduct {
  name: string
  selling_price: string
  current_stock: string
}

const EMPTY_ROW: DraftProduct = { name: '', selling_price: '', current_stock: '' }

export default function ProductOnboardingPage() {
  const router = useRouter()
  const [mode, setMode] = useState<'manual' | 'csv'>('manual')
  const [rows, setRows] = useState<DraftProduct[]>([{ ...EMPTY_ROW }])
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  const [csvResult, setCsvResult] = useState<{ imported: number; skipped: number } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function updateRow(index: number, field: keyof DraftProduct, value: string) {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, [field]: value } : r)))
  }

  function addRow() {
    if (rows.length >= 5) return
    setRows((prev) => [...prev, { ...EMPTY_ROW }])
  }

  function removeRow(index: number) {
    setRows((prev) => prev.filter((_, i) => i !== index))
  }

  const validRows = rows.filter((r) => r.name.trim() && r.selling_price.trim())

  async function handleSaveManual() {
    if (validRows.length === 0) {
      router.push('/dashboard')
      return
    }
    setIsSaving(true)
    setError('')
    try {
      for (const row of validRows) {
        await createProduct({
          name: row.name.trim(),
          selling_price: row.selling_price.trim(),
          current_stock: row.current_stock.trim() || '0',
        })
      }
      router.push('/dashboard')
    } catch (err) {
      setError(apiErrorMessage(err, COPY.ONBOARD_SAVE_ERROR))
      setIsSaving(false)
    }
  }

  async function handleCsvUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setIsSaving(true)
    setError('')
    setCsvResult(null)
    try {
      const result = await importProductsCsv(file)
      setCsvResult({ imported: result.imported, skipped: result.skipped })
    } catch (err) {
      setError(apiErrorMessage(err, COPY.ONBOARD_CSV_UPLOAD_ERROR))
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <main className="grid-bg" style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--sp-5)' }}>
      <Deepfield position="fixed" zIndex={-1} opacity={0.25} />
      <div className="card" style={{ width: '100%', maxWidth: 480 }}>
        <h2 style={{ marginBottom: 'var(--sp-2)' }}>{COPY.ONBOARD_TITLE}</h2>
        <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-5)' }}>
          {COPY.ONBOARD_SUBTITLE}
        </p>

        <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-5)' }}>
          <button type="button" className={mode === 'manual' ? 'btn-primary' : 'btn-secondary'} onClick={() => setMode('manual')}>
            {COPY.ONBOARD_MANUAL_TAB}
          </button>
          <button type="button" className={mode === 'csv' ? 'btn-primary' : 'btn-secondary'} onClick={() => setMode('csv')}>
            {COPY.ONBOARD_CSV_TAB}
          </button>
        </div>

        {mode === 'manual' && (
          <>
            {rows.map((row, i) => (
              <div key={i} className="card-stat" style={{ marginBottom: 'var(--sp-3)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--sp-2)' }}>
                  <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.ONBOARD_PRODUCT_LABEL.replace('{n}', String(i + 1))}</span>
                  {rows.length > 1 && (
                    <button type="button" className="btn-ghost" onClick={() => removeRow(i)} style={{ padding: 0, fontSize: 'var(--fs-xs)' }}>
                      {COPY.ONBOARD_REMOVE}
                    </button>
                  )}
                </div>
                <input
                  className="input"
                  placeholder={COPY.ONBOARD_NAME_PLACEHOLDER}
                  value={row.name}
                  onChange={(e) => updateRow(i, 'name', e.target.value)}
                  style={{ marginBottom: 'var(--sp-2)' }}
                />
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-2)' }}>
                  <input
                    className="input"
                    placeholder={COPY.ONBOARD_PRICE_PLACEHOLDER}
                    inputMode="decimal"
                    value={row.selling_price}
                    onChange={(e) => updateRow(i, 'selling_price', e.target.value)}
                  />
                  <input
                    className="input"
                    placeholder={COPY.ONBOARD_QTY_PLACEHOLDER}
                    inputMode="numeric"
                    value={row.current_stock}
                    onChange={(e) => updateRow(i, 'current_stock', e.target.value)}
                  />
                </div>
              </div>
            ))}

            {rows.length < 5 && (
              <button type="button" className="btn-secondary" onClick={addRow} style={{ width: '100%', justifyContent: 'center', marginBottom: 'var(--sp-5)' }}>
                {COPY.ONBOARD_ADD_ANOTHER}
              </button>
            )}

            {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-3)' }}>{error}</p>}

            <div style={{ display: 'flex', gap: 'var(--sp-2)', marginTop: 'var(--sp-4)' }}>
              <button type="button" className="btn-ghost" onClick={() => router.push('/dashboard')} disabled={isSaving}>
                {COPY.ONBOARD_SKIP}
              </button>
              <button type="button" className="btn-primary" onClick={handleSaveManual} disabled={isSaving} style={{ flex: 1, justifyContent: 'center' }}>
                {isSaving ? COPY.ONBOARD_SAVING : COPY.ONBOARD_SAVE_CONTINUE.replace('{count}', String(validRows.length))}
              </button>
            </div>
          </>
        )}

        {mode === 'csv' && (
          <div>
            <div className="card-terminal" style={{ marginBottom: 'var(--sp-4)' }}>
              {COPY.ONBOARD_CSV_REQUIRED_COLS} <strong>name, selling_price</strong><br />
              {COPY.ONBOARD_CSV_OPTIONAL_COLS}
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleCsvUpload}
              style={{ display: 'none' }}
            />
            <button
              type="button"
              className="btn-secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={isSaving}
              style={{ width: '100%', justifyContent: 'center', marginBottom: 'var(--sp-4)' }}
            >
              {isSaving ? COPY.ONBOARD_CSV_UPLOADING : COPY.ONBOARD_CSV_CHOOSE_FILE}
            </button>

            {csvResult && (
              <div className="card-accent" style={{ marginBottom: 'var(--sp-4)' }}>
                <p>{COPY.ONBOARD_CSV_IMPORTED.replace('{count}', String(csvResult.imported))}</p>
                {csvResult.skipped > 0 && <p style={{ color: 'var(--color-muted)' }}>{COPY.ONBOARD_CSV_SKIPPED.replace('{count}', String(csvResult.skipped))}</p>}
              </div>
            )}

            {error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-3)' }}>{error}</p>}

            <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
              <button type="button" className="btn-ghost" onClick={() => router.push('/dashboard')}>
                {COPY.ONBOARD_SKIP}
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={() => router.push('/dashboard')}
                disabled={!csvResult}
                style={{ flex: 1, justifyContent: 'center' }}
              >
                {COPY.ONBOARD_CONTINUE_DASHBOARD}
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}
