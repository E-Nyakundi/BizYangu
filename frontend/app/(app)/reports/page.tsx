'use client'

/**
 * BizYangu — Reports (Phase 5).
 * Four tabs: Daily (single day + WhatsApp EOD share), Period (date range +
 * revenue-by-day chart), Products (performance/margin), Losses (loss +
 * damage value). Period/Products/Losses share one date range so switching
 * tabs doesn't reset what you were looking at.
 */

import { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { useAuthStore } from '@/lib/auth'
import { COPY } from '@/lib/copy'
import { shareText } from '@/lib/share-text'
import {
  getDailyReport, getPeriodReport, getProductPerformance, getLossReport, getEodSummary, getGrowthReport,
  type DailyReport, type PeriodReport, type ProductPerformanceReport, type LossReport, type GrowthReport,
} from '@/lib/reports'

type Tab = 'daily' | 'period' | 'growth' | 'products' | 'losses'

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}
function daysAgoStr(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

function GrowthBadge({ pct }: { pct: number | null }) {
  if (pct === null) {
    return <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.REPORTS_GROWTH_NO_COMPARISON}</span>
  }
  const positive = pct >= 0
  return (
    <span
      className="mono"
      style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, color: positive ? 'var(--color-teal)' : 'var(--color-error)' }}
    >
      {positive ? '▲' : '▼'} {Math.abs(pct).toFixed(1)}% {COPY.REPORTS_GROWTH_VS_PREVIOUS}
    </span>
  )
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--sp-1) 0' }}>
      <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{label}</span>
      <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 600 }}>{value}</span>
    </div>
  )
}

export default function ReportsPage() {
  const user = useAuthStore((s) => s.user)
  const canManage = user?.role === 'OWNER' || user?.role === 'MANAGER'
  const [manageExpanded, setManageExpanded] = useState(false)

  const [tab, setTab] = useState<Tab>('daily')

  const [date, setDate] = useState(todayStr())
  const [start, setStart] = useState(daysAgoStr(29))
  const [end, setEnd] = useState(todayStr())

  const [daily, setDaily] = useState<DailyReport | null>(null)
  const [period, setPeriod] = useState<PeriodReport | null>(null)
  const [growth, setGrowth] = useState<GrowthReport | null>(null)
  const [products, setProducts] = useState<ProductPerformanceReport | null>(null)
  const [losses, setLosses] = useState<LossReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [shareStatus, setShareStatus] = useState('')

  useEffect(() => {
    setLoading(true)
    setError(false)
    const done = () => setLoading(false)
    const fail = () => { setError(true); setLoading(false) }

    if (tab === 'daily') getDailyReport(date).then(setDaily).then(done).catch(fail)
    if (tab === 'period') getPeriodReport(start, end).then(setPeriod).then(done).catch(fail)
    if (tab === 'growth') getGrowthReport(start, end).then(setGrowth).then(done).catch(fail)
    if (tab === 'products') getProductPerformance(start, end).then(setProducts).then(done).catch(fail)
    if (tab === 'losses') getLossReport(start, end).then(setLosses).then(done).catch(fail)
  }, [tab, date, start, end])

  function setQuickRange(days: number) {
    setStart(daysAgoStr(days - 1))
    setEnd(todayStr())
  }

  async function handleShareEod() {
    setShareStatus('')
    const summary = await getEodSummary(date)
    await shareText(summary.whatsapp_text)
    setShareStatus(COPY.REPORTS_SHARE_COPIED)
  }

  return (
    <main style={{ padding: 'var(--sp-6) var(--sp-5)', maxWidth: 720 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-5)' }}>
        <h1 style={{ fontSize: 'var(--fs-lg)' }}>{COPY.REPORTS_TITLE}</h1>
        <Link href="/dashboard" className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }}>{COPY.REPORTS_GO_HOME}</Link>
      </div>

      {/* E19: on desktop, Payments/Creditors are already an always-expanded
          nested tree under Reports in the side nav (see layout.tsx) — no
          need to repeat them here. On mobile, the bottom nav can't show
          nesting, so this collapsed-by-default accordion is the mobile
          equivalent: same links, collapsed until tapped instead of always
          visible. Same owner/manager gate either way. */}
      {canManage && (
        <div className="mobile-only" style={{ marginBottom: 'var(--sp-5)' }}>
          <button
            onClick={() => setManageExpanded((v) => !v)}
            className="btn-ghost"
            style={{
              fontSize: 'var(--fs-xs)',
              color: 'var(--color-muted)',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--sp-2)',
              width: '100%',
              justifyContent: 'flex-start',
            }}
            aria-expanded={manageExpanded}
          >
            <span style={{ transform: manageExpanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>▸</span>
            {COPY.REPORTS_MANAGE_TITLE}
          </button>
          {manageExpanded && (
            <div className="nav-nested" style={{ marginTop: 'var(--sp-2)' }}>
              <Link href="/payments" className="btn-ghost" style={{ fontSize: 'var(--fs-xs)', display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', textDecoration: 'none' }}>
                <span>💳</span> {COPY.REPORTS_MANAGE_PAYMENTS}
              </Link>
              <Link href="/creditors" className="btn-ghost" style={{ fontSize: 'var(--fs-xs)', display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', textDecoration: 'none' }}>
                <span>🤝</span> {COPY.REPORTS_MANAGE_CREDITORS}
              </Link>
            </div>
          )}
        </div>
      )}

      {/* Tabs
          E19 note (pre-pilot backlog item 22): Payments/Creditors — the
          other two screens folded under this section's umbrella via the
          nav/accordion above — carry icons (💳 🤝). These five report tabs
          previously didn't, which read as inconsistent. Decision: icons
          everywhere, so every tab here gets one too, same treatment. */}
      <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-4)', flexWrap: 'wrap' }}>
        {([
          ['daily', '📅', COPY.REPORTS_TAB_DAILY],
          ['period', '🗓️', COPY.REPORTS_TAB_PERIOD],
          ['growth', '📈', COPY.REPORTS_TAB_GROWTH],
          ['products', '🏷️', COPY.REPORTS_TAB_PRODUCTS],
          ['losses', '📉', COPY.REPORTS_TAB_LOSSES],
        ] as [Tab, string, string][]).map(([key, icon, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={tab === key ? 'btn-primary' : 'btn-ghost'}
            style={{ fontSize: 'var(--fs-xs)', display: 'flex', alignItems: 'center', gap: 'var(--sp-1)' }}
          >
            <span aria-hidden="true">{icon}</span> {label}
          </button>
        ))}
      </div>

      {/* Date controls */}
      {tab === 'daily' ? (
        <div style={{ marginBottom: 'var(--sp-4)' }}>
          <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
            {COPY.REPORTS_DATE_LABEL}
          </label>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} max={todayStr()} />
        </div>
      ) : (
        <div style={{ marginBottom: 'var(--sp-4)' }}>
          <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: 'var(--sp-2)', flexWrap: 'wrap' }}>
            <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }} onClick={() => setQuickRange(1)}>{COPY.REPORTS_QUICK_TODAY}</button>
            <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }} onClick={() => setQuickRange(7)}>{COPY.REPORTS_QUICK_7D}</button>
            <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }} onClick={() => setQuickRange(30)}>{COPY.REPORTS_QUICK_30D}</button>
          </div>
          <div style={{ display: 'flex', gap: 'var(--sp-3)' }}>
            <div>
              <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                {COPY.REPORTS_START_LABEL}
              </label>
              <input className="input" type="date" value={start} onChange={(e) => setStart(e.target.value)} max={end} />
            </div>
            <div>
              <label style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', display: 'block', marginBottom: 'var(--sp-1)' }}>
                {COPY.REPORTS_END_LABEL}
              </label>
              <input className="input" type="date" value={end} onChange={(e) => setEnd(e.target.value)} max={todayStr()} min={start} />
            </div>
          </div>
        </div>
      )}

      {loading && <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.REPORTS_LOADING}</p>}
      {!loading && error && <p style={{ color: 'var(--color-error)', fontSize: 'var(--fs-xs)' }}>{COPY.REPORTS_ERROR}</p>}

      {/* ── Daily tab ── */}
      {!loading && !error && tab === 'daily' && daily && (
        <>
          <div className="card" style={{ padding: 'var(--sp-4)', marginBottom: 'var(--sp-3)' }}>
            <StatRow label={COPY.REPORTS_NET_REVENUE_LABEL} value={`KES ${Number(daily.net_revenue).toLocaleString()}`} />
            <StatRow label={COPY.REPORTS_GROSS_LABEL} value={`KES ${Number(daily.gross_revenue).toLocaleString()}`} />
            <StatRow label={COPY.REPORTS_REFUNDED_LABEL} value={`KES ${Number(daily.refunded_amount).toLocaleString()}`} />
            <StatRow label={COPY.REPORTS_TXN_COUNT_LABEL} value={String(daily.transaction_count)} />
            <StatRow label={COPY.REPORTS_AVG_LABEL} value={`KES ${Number(daily.average_transaction).toLocaleString()}`} />
            {daily.voided_count > 0 && <StatRow label={COPY.REPORTS_VOIDED_LABEL} value={String(daily.voided_count)} />}
          </div>

          <div className="card" style={{ padding: 'var(--sp-4)', marginBottom: 'var(--sp-3)' }}>
            <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
              {COPY.REPORTS_PAYMENT_SPLIT_TITLE}
            </div>
            <StatRow label={COPY.DASHBOARD_CASH_LABEL} value={`KES ${Number(daily.cash_total).toLocaleString()}`} />
            <StatRow label={COPY.DASHBOARD_MPESA_LABEL} value={`KES ${Number(daily.mpesa_total).toLocaleString()}`} />
            {Number(daily.credit_total) > 0 && <StatRow label={COPY.DASHBOARD_CREDIT_LABEL} value={`KES ${Number(daily.credit_total).toLocaleString()}`} />}
            {Number(daily.mixed_total) > 0 && <StatRow label={COPY.DASHBOARD_MIXED_LABEL} value={`KES ${Number(daily.mixed_total).toLocaleString()}`} />}
          </div>

          <div className="card" style={{ padding: 'var(--sp-4)', marginBottom: 'var(--sp-3)' }}>
            <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
              {COPY.REPORTS_TOP_PRODUCTS_TITLE}
            </div>
            {daily.top_products.length === 0 ? (
              <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.REPORTS_NO_PRODUCTS_SOLD}</p>
            ) : (
              daily.top_products.map((p, i) => (
                <div key={p.product_id} style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--sp-1) 0' }}>
                  <span style={{ fontSize: 'var(--fs-sm)' }}>{i + 1}. {p.name}</span>
                  <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                    {Number(p.quantity_sold)} {p.unit} · KES {Number(p.revenue).toLocaleString()}
                  </span>
                </div>
              ))
            )}
          </div>

          <button className="btn-primary" style={{ width: '100%', fontSize: 'var(--fs-xs)' }} onClick={handleShareEod}>
            {COPY.REPORTS_SHARE_WHATSAPP_BTN}
          </button>
          {shareStatus && <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-teal)', marginTop: 'var(--sp-2)', textAlign: 'center' }}>{shareStatus}</p>}
        </>
      )}

      {/* ── Period tab ── */}
      {!loading && !error && tab === 'period' && period && (
        <>
          <div className="card" style={{ padding: 'var(--sp-4)', marginBottom: 'var(--sp-3)' }}>
            <StatRow label={COPY.REPORTS_NET_REVENUE_LABEL} value={`KES ${Number(period.net_revenue).toLocaleString()}`} />
            <StatRow label={COPY.REPORTS_GROSS_LABEL} value={`KES ${Number(period.gross_revenue).toLocaleString()}`} />
            <StatRow label={COPY.REPORTS_REFUNDED_LABEL} value={`KES ${Number(period.refunded_amount).toLocaleString()}`} />
            <StatRow label={COPY.REPORTS_TXN_COUNT_LABEL} value={String(period.transaction_count)} />
            <StatRow label={COPY.REPORTS_AVG_LABEL} value={`KES ${Number(period.average_transaction).toLocaleString()}`} />
          </div>

          {period.daily_breakdown.length > 0 && (
            <div className="card" style={{ padding: 'var(--sp-4)', marginBottom: 'var(--sp-3)' }}>
              <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
                {COPY.REPORTS_DAILY_CHART_TITLE}
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={period.daily_breakdown}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-3)" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--color-muted)' }} tickFormatter={(d) => d.slice(5)} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--color-muted)' }} />
                  <Tooltip
                    formatter={(value: number) => [`KES ${Number(value).toLocaleString()}`, COPY.REPORTS_NET_REVENUE_LABEL]}
                    contentStyle={{ background: 'var(--surface-2)', border: '1px solid var(--surface-3)', fontSize: 12 }}
                  />
                  <Bar dataKey="revenue" fill="var(--color-teal)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="card" style={{ padding: 'var(--sp-4)' }}>
            <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
              {COPY.REPORTS_TOP_PRODUCTS_TITLE}
            </div>
            {period.top_products.length === 0 ? (
              <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.REPORTS_NO_PRODUCTS_SOLD}</p>
            ) : (
              period.top_products.map((p, i) => (
                <div key={p.product_id} style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--sp-1) 0' }}>
                  <span style={{ fontSize: 'var(--fs-sm)' }}>{i + 1}. {p.name}</span>
                  <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                    {Number(p.quantity_sold)} {p.unit} · KES {Number(p.revenue).toLocaleString()}
                  </span>
                </div>
              ))
            )}
          </div>
        </>
      )}

      {/* ── Growth tab (Phase 7) ── */}
      {!loading && !error && tab === 'growth' && growth && (
        <>
          <div className="card" style={{ padding: 'var(--sp-4)', marginBottom: 'var(--sp-3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--sp-2)' }}>
              <div>
                <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.REPORTS_GROWTH_CURRENT_PERIOD_LABEL}</div>
                <div style={{ fontSize: 'var(--fs-lg)', fontWeight: 700 }}>
                  KES {Number(growth.current_period.net_revenue).toLocaleString()}
                </div>
                <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                  {growth.current_period.transaction_count} {COPY.REPORTS_TXN_COUNT_LABEL.toLowerCase()}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <GrowthBadge pct={growth.revenue_growth_pct} />
                <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginTop: 'var(--sp-1)' }}>
                  {COPY.REPORTS_GROWTH_PREVIOUS_PERIOD_LABEL}: KES {Number(growth.previous_period.net_revenue).toLocaleString()}
                </div>
              </div>
            </div>
          </div>

          {growth.daily_breakdown.length === 0 ? (
            <div className="card" style={{ padding: 'var(--sp-4)', marginBottom: 'var(--sp-3)' }}>
              <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.REPORTS_GROWTH_NO_DATA}</p>
            </div>
          ) : (
            <div className="card" style={{ padding: 'var(--sp-4)', marginBottom: 'var(--sp-3)', overflow: 'hidden' }}>
              <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
                {COPY.REPORTS_GROWTH_REVENUE_CHART_TITLE}
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={growth.daily_breakdown}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-3)" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--color-muted)' }} tickFormatter={(d) => d.slice(5)} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--color-muted)' }} />
                  <Tooltip
                    formatter={(value: number) => [`KES ${Number(value).toLocaleString()}`, COPY.REPORTS_NET_REVENUE_LABEL]}
                    contentStyle={{ background: 'var(--surface-2)', border: '1px solid var(--surface-3)', fontSize: 12 }}
                  />
                  <Line type="monotone" dataKey="revenue" stroke="var(--color-teal)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Margin trend only renders for goods-type businesses — a service
              business (no stock-tracked products, no cost_price data at all)
              shouldn't see stock/margin framing that doesn't apply to it. */}
          {growth.business_mode === 'goods' && (
            <div className="card" style={{ padding: 'var(--sp-4)', overflow: 'hidden' }}>
              <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
                {COPY.REPORTS_GROWTH_MARGIN_CHART_TITLE}
              </div>
              {!growth.has_margin_data ? (
                <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.REPORTS_GROWTH_NO_MARGIN_DATA}</p>
              ) : (
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={growth.margin_trend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-3)" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--color-muted)' }} tickFormatter={(d) => d.slice(5)} />
                    <YAxis tick={{ fontSize: 10, fill: 'var(--color-muted)' }} />
                    <Tooltip
                      formatter={(value: number) => [`KES ${Number(value).toLocaleString()}`, COPY.REPORTS_MARGIN_COL]}
                      contentStyle={{ background: 'var(--surface-2)', border: '1px solid var(--surface-3)', fontSize: 12 }}
                    />
                    <Line type="monotone" dataKey="margin" stroke="var(--color-violet)" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          )}
        </>
      )}

      {/* ── Products tab ── */}
      {!loading && !error && tab === 'products' && products && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {products.products.length === 0 ? (
            <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', padding: 'var(--sp-4)' }}>
              {COPY.REPORTS_NO_PRODUCTS_SOLD}
            </p>
          ) : (
            <table style={{ width: '100%', fontSize: 'var(--fs-xs)', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--surface-3)' }}>
                  <th style={{ textAlign: 'left', padding: 'var(--sp-2) var(--sp-3)', color: 'var(--color-muted)' }}>{COPY.REPORTS_PRODUCT_COL}</th>
                  <th style={{ textAlign: 'right', padding: 'var(--sp-2) var(--sp-3)', color: 'var(--color-muted)' }}>{COPY.REPORTS_QTY_COL}</th>
                  <th style={{ textAlign: 'right', padding: 'var(--sp-2) var(--sp-3)', color: 'var(--color-muted)' }}>{COPY.REPORTS_REVENUE_COL}</th>
                  <th style={{ textAlign: 'right', padding: 'var(--sp-2) var(--sp-3)', color: 'var(--color-muted)' }}>{COPY.REPORTS_MARGIN_COL}</th>
                </tr>
              </thead>
              <tbody>
                {products.products.map((p) => (
                  <tr key={p.product_id} style={{ borderBottom: '1px solid var(--surface-2)' }}>
                    <td style={{ padding: 'var(--sp-2) var(--sp-3)' }}>{p.name}</td>
                    <td style={{ textAlign: 'right', padding: 'var(--sp-2) var(--sp-3)' }} className="mono">{Number(p.quantity_sold)} {p.unit}</td>
                    <td style={{ textAlign: 'right', padding: 'var(--sp-2) var(--sp-3)' }} className="mono">{Number(p.revenue).toLocaleString()}</td>
                    <td style={{ textAlign: 'right', padding: 'var(--sp-2) var(--sp-3)' }} className="mono">
                      {p.margin_pct != null ? (
                        <span style={{ color: p.margin_pct >= 0 ? 'var(--color-teal)' : 'var(--color-error)' }}>
                          {p.margin_pct.toFixed(0)}%
                        </span>
                      ) : COPY.REPORTS_MARGIN_NOT_SET}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Losses tab ── */}
      {!loading && !error && tab === 'losses' && losses && (
        <>
          <div className="card" style={{ padding: 'var(--sp-4)', marginBottom: 'var(--sp-3)' }}>
            <StatRow label={COPY.REPORTS_TOTAL_LOSS_VALUE} value={`KES ${Number(losses.total_estimated_value).toLocaleString()}`} />
          </div>

          {losses.by_type.length > 0 && (
            <div className="card" style={{ padding: 'var(--sp-4)', marginBottom: 'var(--sp-3)' }}>
              <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
                {COPY.REPORTS_LOSS_BY_TYPE_TITLE}
              </div>
              {losses.by_type.map((row) => (
                <div key={row.movement_type} style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--sp-1) 0' }}>
                  <span style={{ fontSize: 'var(--fs-sm)' }}>
                    {row.movement_type === 'DAMAGE' ? COPY.STOCK_MOVEMENT_DAMAGE : COPY.STOCK_MOVEMENT_LOSS}
                  </span>
                  <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-error)' }}>
                    KES {Number(row.estimated_value).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}

          {losses.by_employee.length > 0 && (
            <div className="card" style={{ padding: 'var(--sp-4)', marginBottom: 'var(--sp-3)' }}>
              <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
                {COPY.REPORTS_LOSS_BY_EMPLOYEE_TITLE}
              </div>
              {losses.by_employee.map((row) => (
                <div key={row.user_id ?? row.name} style={{ display: 'flex', justifyContent: 'space-between', padding: 'var(--sp-1) 0' }}>
                  <span style={{ fontSize: 'var(--fs-sm)' }}>{row.name}</span>
                  <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-error)' }}>
                    KES {Number(row.estimated_value).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {losses.by_product.length === 0 ? (
              <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', padding: 'var(--sp-4)' }}>
                {COPY.REPORTS_NO_LOSSES}
              </p>
            ) : (
              <table style={{ width: '100%', fontSize: 'var(--fs-xs)', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--surface-3)' }}>
                    <th style={{ textAlign: 'left', padding: 'var(--sp-2) var(--sp-3)', color: 'var(--color-muted)' }}>{COPY.REPORTS_PRODUCT_COL}</th>
                    <th style={{ textAlign: 'right', padding: 'var(--sp-2) var(--sp-3)', color: 'var(--color-muted)' }}>{COPY.REPORTS_QTY_COL}</th>
                    <th style={{ textAlign: 'right', padding: 'var(--sp-2) var(--sp-3)', color: 'var(--color-muted)' }}>{COPY.REPORTS_COST_COL}</th>
                  </tr>
                </thead>
                <tbody>
                  {losses.by_product.map((p) => (
                    <tr key={p.product_id} style={{ borderBottom: '1px solid var(--surface-2)' }}>
                      <td style={{ padding: 'var(--sp-2) var(--sp-3)' }}>{p.name}</td>
                      <td style={{ textAlign: 'right', padding: 'var(--sp-2) var(--sp-3)' }} className="mono">{Number(p.quantity_lost)} {p.unit}</td>
                      <td style={{ textAlign: 'right', padding: 'var(--sp-2) var(--sp-3)' }} className="mono">
                        <span style={{ color: 'var(--color-error)' }}>KES {Number(p.estimated_value).toLocaleString()}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      <div style={{ marginTop: 'var(--sp-5)', display: 'flex', gap: 'var(--sp-3)' }}>
        <Link href="/sell/transactions" className="btn-secondary" style={{ fontSize: 'var(--fs-xs)' }}>
          {COPY.REPORTS_VIEW_TRANSACTIONS}
        </Link>
        <Link href="/stock" className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }}>
          {COPY.REPORTS_VIEW_STOCK}
        </Link>
      </div>
    </main>
  )
}