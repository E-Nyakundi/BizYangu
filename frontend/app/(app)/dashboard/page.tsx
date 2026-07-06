'use client'

/**
 * BizYangu — Dashboard (Phase 5).
 * Today's revenue, transaction count, payment split, top sellers, and a
 * stock alert strip — all from GET /reports/dashboard/. SELL MODE stays
 * the primary action; stats sit below it, not instead of it.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useAuthStore, logout } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { COPY } from '@/lib/copy'
import { getDashboard, type DashboardReport } from '@/lib/reports'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'
const WS_BASE = API_BASE.replace(/^http/, 'ws').replace('/api/v1', '')

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card" style={{ padding: 'var(--sp-3)' }}>
      <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>{label}</div>
      <div style={{ fontSize: 'var(--fs-md)', fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

export default function DashboardPage() {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)

  const [report, setReport] = useState<DashboardReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [isLive, setIsLive] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const refetch = useCallback(() => {
    getDashboard()
      .then((r) => { setReport(r); setError(false) })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    refetch()
  }, [refetch])

  // ── Live feed: a 'dashboard.tick' event over ws/dashboard/{business_id}/
  // means a sale/refund/void/stock-movement just landed elsewhere (another
  // till, another staff member's phone). It carries no payload beyond a
  // reason tag — we just refetch GET /reports/dashboard/ rather than
  // duplicating its aggregation logic client-side. No live connection is
  // fine too: the numbers just update on next manual page load instead.
  useEffect(() => {
    if (!user?.business_id) return

    const ws = new WebSocket(`${WS_BASE}/ws/dashboard/${user.business_id}/`)
    wsRef.current = ws
    ws.onopen = () => setIsLive(true)
    ws.onclose = () => setIsLive(false)
    ws.onerror = () => setIsLive(false) // silent — manual refresh is the fallback
    ws.onmessage = () => refetch()

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [user?.business_id, refetch])

  async function handleLogout() {
    await logout()
    setUser(null)
    router.push('/login')
  }

  const hour = new Date().getHours()
  const greeting = hour < 12 ? COPY.DASHBOARD_GREETING_MORNING : hour < 17 ? COPY.DASHBOARD_GREETING_AFTERNOON : COPY.DASHBOARD_GREETING_EVENING

  const changePct = report?.revenue_change_pct
  const changeColor = changePct == null ? 'var(--color-muted)' : changePct >= 0 ? 'var(--color-teal)' : 'var(--color-error)'
  const changeSign = changePct != null && changePct > 0 ? '+' : ''

  return (
    <main style={{ padding: 'var(--sp-6) var(--sp-5)', maxWidth: 720 }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--sp-6)' }}>
        <div>
          <h1 style={{ fontSize: 'var(--fs-lg)', marginBottom: 'var(--sp-1)' }}>
            {greeting}, {user?.name?.split(' ')[0] || COPY.DASHBOARD_DEFAULT_NAME} 👋
          </h1>
          <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>
            {user?.business_name || COPY.DASHBOARD_DEFAULT_BUSINESS}
          </p>
        </div>
        <button className="btn-ghost" onClick={handleLogout} style={{ fontSize: 'var(--fs-xs)' }}>
          {COPY.SETTINGS_LOGOUT}
        </button>
      </div>

      {/* Primary CTA — SELL MODE */}
      <Link href="/sell" style={{ textDecoration: 'none', display: 'block', marginBottom: 'var(--sp-5)' }}>
        <div style={{
          background: 'var(--color-teal)',
          borderRadius: 'var(--radius-card)',
          padding: 'var(--sp-6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          transition: 'opacity 0.15s',
        }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
        >
          <div>
            <div className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'rgba(0,0,0,0.6)', marginBottom: 'var(--sp-1)' }}>
              {COPY.DASHBOARD_SELL_ACTION}
            </div>
            <div style={{ fontSize: 'var(--fs-lg)', fontWeight: 700, color: '#000', lineHeight: 1.1 }}>
              SELL MODE
            </div>
            <div style={{ fontSize: 'var(--fs-xs)', color: 'rgba(0,0,0,0.6)', marginTop: 'var(--sp-1)' }}>
              {COPY.DASHBOARD_SELL_DESC}
            </div>
          </div>
          <span style={{ fontSize: 48 }}>🛒</span>
        </div>
      </Link>

      {/* Quick actions grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-3)', marginBottom: 'var(--sp-5)' }}>
        <Link href="/sell/transactions" style={{ textDecoration: 'none' }}>
          <div className="card" style={{ cursor: 'pointer', textAlign: 'center' }}>
            <div style={{ fontSize: 28, marginBottom: 'var(--sp-2)' }}>📋</div>
            <div style={{ fontWeight: 600, fontSize: 'var(--fs-sm)' }}>{COPY.DASHBOARD_TXN_TODAY}</div>
            <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.DASHBOARD_TXN_TODAY_DESC}</div>
          </div>
        </Link>
        <Link href="/stock" style={{ textDecoration: 'none' }}>
          <div className="card" style={{ cursor: 'pointer', textAlign: 'center' }}>
            <div style={{ fontSize: 28, marginBottom: 'var(--sp-2)' }}>📦</div>
            <div style={{ fontWeight: 600, fontSize: 'var(--fs-sm)' }}>{COPY.DASHBOARD_STOCK_CARD}</div>
            <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.DASHBOARD_STOCK_CARD_DESC}</div>
          </div>
        </Link>
      </div>

      {/* Today's stats */}
      {loading && (
        <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)', marginBottom: 'var(--sp-5)' }}>
          {COPY.DASHBOARD_STATS_LOADING}
        </p>
      )}

      {!loading && error && (
        <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-xs)', marginBottom: 'var(--sp-5)' }}>
          {COPY.DASHBOARD_STATS_ERROR}
        </p>
      )}

      {!loading && !error && report && (
        <>
          {/* Revenue hero card */}
          <div className="card" style={{ marginBottom: 'var(--sp-3)', padding: 'var(--sp-4)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-1)' }}>
              <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                {COPY.DASHBOARD_TODAY_REVENUE}
              </span>
              {isLive && (
                <span
                  title={COPY.DASHBOARD_LIVE_LABEL}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--color-teal)' }}
                >
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-teal)', display: 'inline-block' }} />
                  {COPY.DASHBOARD_LIVE_LABEL}
                </span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--sp-2)' }}>
              <div style={{ fontSize: 'var(--fs-xl)', fontWeight: 700 }}>
                KES {Number(report.net_revenue).toLocaleString()}
              </div>
              {changePct != null && (
                <span style={{ fontSize: 'var(--fs-xs)', color: changeColor }}>
                  {changeSign}{changePct.toFixed(0)}% {COPY.DASHBOARD_VS_YESTERDAY}
                </span>
              )}
            </div>
            {Number(report.refunded_amount) > 0 && (
              <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-amber)', marginTop: 'var(--sp-1)' }}>
                {COPY.DASHBOARD_REFUNDED_LABEL}: KES {Number(report.refunded_amount).toLocaleString()}
              </div>
            )}
          </div>

          {/* Stat grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-3)', marginBottom: 'var(--sp-3)' }}>
            <StatCard label={COPY.DASHBOARD_TXN_COUNT_LABEL} value={String(report.transaction_count)} />
            <StatCard label={COPY.DASHBOARD_AVG_SALE_LABEL} value={`KES ${Number(report.average_transaction).toLocaleString()}`} />
          </div>

          {/* Payment split */}
          <div className="card" style={{ marginBottom: 'var(--sp-3)', padding: 'var(--sp-4)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-3)' }}>
              <div>
                <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.DASHBOARD_CASH_LABEL}</div>
                <div style={{ fontWeight: 700 }}>KES {Number(report.cash_total).toLocaleString()}</div>
              </div>
              <div>
                <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.DASHBOARD_MPESA_LABEL}</div>
                <div style={{ fontWeight: 700 }}>KES {Number(report.mpesa_total).toLocaleString()}</div>
              </div>
              {Number(report.credit_total) > 0 && (
                <div>
                  <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.DASHBOARD_CREDIT_LABEL}</div>
                  <div style={{ fontWeight: 700 }}>KES {Number(report.credit_total).toLocaleString()}</div>
                </div>
              )}
              {Number(report.mixed_total) > 0 && (
                <div>
                  <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.DASHBOARD_MIXED_LABEL}</div>
                  <div style={{ fontWeight: 700 }}>KES {Number(report.mixed_total).toLocaleString()}</div>
                </div>
              )}
            </div>
          </div>

          {/* Top products */}
          <div className="card" style={{ marginBottom: 'var(--sp-3)', padding: 'var(--sp-4)' }}>
            <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
              {COPY.DASHBOARD_TOP_PRODUCTS_TITLE}
            </div>
            {report.top_products.length === 0 ? (
              <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.DASHBOARD_NO_SALES_YET}</p>
            ) : (
              report.top_products.map((p, i) => (
                <div key={p.product_id} style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--sp-1) 0' }}>
                  <span style={{ fontSize: 'var(--fs-sm)' }}>{i + 1}. {p.name}</span>
                  <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                    {Number(p.quantity_sold)} {p.unit} · KES {Number(p.revenue).toLocaleString()}
                  </span>
                </div>
              ))
            )}
          </div>

          {/* Stock alert */}
          <div
            className="card"
            style={{
              marginBottom: 'var(--sp-5)', padding: 'var(--sp-4)',
              borderColor: report.stock_alert.out_of_stock_count > 0 ? 'var(--color-error)' : undefined,
            }}
          >
            <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
              {COPY.DASHBOARD_STOCK_ALERT_TITLE}
            </div>
            {report.stock_alert.low_stock_count === 0 && report.stock_alert.out_of_stock_count === 0 ? (
              <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.DASHBOARD_NO_STOCK_ALERTS}</p>
            ) : (
              <>
                <div style={{ display: 'flex', gap: 'var(--sp-3)', marginBottom: 'var(--sp-2)' }}>
                  {report.stock_alert.out_of_stock_count > 0 && (
                    <span className="badge badge-error" style={{ fontSize: 'var(--fs-xs)' }}>
                      {COPY.DASHBOARD_OUT_OF_STOCK_COUNT.replace('{count}', String(report.stock_alert.out_of_stock_count))}
                    </span>
                  )}
                  {report.stock_alert.low_stock_count > 0 && (
                    <span className="badge" style={{ fontSize: 'var(--fs-xs)', background: 'rgba(251,191,36,0.15)', color: 'var(--color-amber)', border: '1px solid var(--color-amber)' }}>
                      {COPY.DASHBOARD_LOW_STOCK_COUNT.replace('{count}', String(report.stock_alert.low_stock_count))}
                    </span>
                  )}
                </div>
                {report.stock_alert.items.slice(0, 3).map((item) => (
                  <div key={item.product_id} style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                    {item.name} — {Number(item.current_stock)} {item.unit}
                  </div>
                ))}
              </>
            )}
          </div>

          <Link href="/reports" className="btn-secondary" style={{ display: 'block', textAlign: 'center', fontSize: 'var(--fs-xs)' }}>
            {COPY.DASHBOARD_VIEW_REPORTS}
          </Link>
        </>
      )}
    </main>
  )
}
