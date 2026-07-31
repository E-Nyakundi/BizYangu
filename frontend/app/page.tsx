'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { api } from '@/lib/api'
import { COPY } from '@/lib/copy'
import Logo from '@/components/Logo'

export default function HomePage() {
  const [apiStatus, setApiStatus] = useState<'checking' | 'ok' | 'error'>('checking')
  const [apiData, setApiData] = useState<Record<string, string> | null>(null)

  useEffect(() => {
    api.get('/health/')
      .then((res) => {
        setApiStatus('ok')
        setApiData(res.data)
      })
      .catch(() => setApiStatus('error'))
  }, [])

  return (
    <main
      style={{
        minHeight: '100dvh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--sp-6)',
        padding: 'var(--sp-8)',
        background: 'var(--surface-0)',
      }}
    >
      {/* Logo / wordmark */}
      <div style={{ textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 'var(--sp-2)' }}>
          <Logo height={22} />
        </div>
        <div
          className="mono"
          style={{
            color: 'var(--color-teal)',
            fontSize: 'var(--fs-xs)',
            letterSpacing: '0.15em',
            marginBottom: 'var(--sp-2)',
          }}
        >
          BIASHARA SYSTEMS
        </div>
        <h1
          style={{
            fontSize: 'var(--fs-2xl)',
            fontWeight: 700,
            letterSpacing: '-0.02em',
            color: 'var(--color-off-white)',
            margin: 0,
          }}
        >
          BizYangu
        </h1>
        <p
          style={{
            fontSize: 'var(--fs-md)',
            color: 'var(--color-muted)',
            marginTop: 'var(--sp-2)',
          }}
        >
          Biashara yako mikononi.
        </p>
      </div>

      {/* API health card */}
      <div className="card-terminal" style={{ minWidth: 320, maxWidth: 480, width: '100%' }}>
        <div style={{ marginBottom: 'var(--sp-3)', color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>
          // api health check
        </div>
        <div>
          <span style={{ color: 'var(--color-muted)' }}>$ </span>
          <span>curl /api/v1/health/</span>
        </div>
        <div style={{ marginTop: 'var(--sp-2)' }}>
          {apiStatus === 'checking' && (
            <span style={{ color: 'var(--color-muted)' }}>checking...</span>
          )}
          {apiStatus === 'ok' && (
            <span style={{ color: 'var(--color-teal)' }}>
              ✓ {JSON.stringify(apiData, null, 0)}
            </span>
          )}
          {apiStatus === 'error' && (
            <span style={{ color: 'var(--color-error)' }}>
              {COPY.HOME_API_ERROR}
            </span>
          )}
        </div>
        <div style={{ marginTop: 'var(--sp-4)', color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>
          v0.1.0 · phase-0 · django + next.js + capacitor▌
        </div>
      </div>

      {/* Nav CTA */}
      <div style={{ display: 'flex', gap: 'var(--sp-3)' }}>
        <Link href="/login" className="btn-primary">
          {COPY.HOME_LOGIN}
        </Link>
        <Link href="/dashboard" className="btn-secondary">
          Dashboard
        </Link>
      </div>
    </main>
  )
}