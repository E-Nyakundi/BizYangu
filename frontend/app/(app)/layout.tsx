'use client'

/**
 * BizYangu — (app) layout.
 * Auth guard + bottom nav on mobile / side nav on wider screens.
 * Demo expiry banner when days_remaining <= 3.
 * "Payments" and "Creditors" nav items visible to OWNER and MANAGER only.
 */

import { useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'
import { useAuthStore } from '@/lib/auth'
import { registerPushNotifications } from '@/lib/push'
import { COPY } from '@/lib/copy'
import Logo from '@/components/Logo'

const NAV_ITEMS = [
  { href: '/dashboard', label: COPY.NAV_HOME, icon: '⊞', roles: null },
  { href: '/sell', label: COPY.NAV_SELL, icon: '🛒', roles: null },
  { href: '/stock', label: COPY.NAV_STOCK, icon: '📦', roles: null },
  { href: '/reports', label: COPY.NAV_REPORTS, icon: '📊', roles: null },
  { href: '/payments', label: COPY.NAV_PAYMENTS, icon: '💳', roles: ['OWNER', 'MANAGER'] as string[] },
  { href: '/creditors', label: COPY.NAV_CREDITORS, icon: '🤝', roles: ['OWNER', 'MANAGER'] as string[] },
  { href: '/settings', label: COPY.NAV_SETTINGS, icon: '⚙', roles: null },
]

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const { user, isInitialized, isLoading, hydrate } = useAuthStore()

  useEffect(() => {
    if (!isInitialized) hydrate()
  }, [isInitialized, hydrate])

  useEffect(() => {
    if (!isInitialized || isLoading) return
    if (!user) {
      router.replace('/login')
    } else if (!user.business_id) {
      router.replace('/setup')
    }
  }, [isInitialized, isLoading, user, router])

  useEffect(() => {
  // Gated behind NEXT_PUBLIC_PUSH_ENABLED — calling PushNotifications.register()
  // with no google-services.json in android/app/ (no Firebase project created
  // yet, per CHANGES.md's known deferred items) throws a native
  // "Default FirebaseApp is not initialized" exception that crashes the whole
  // app process, not a JS error the try/catch in lib/push.ts can catch.
  // Flip NEXT_PUBLIC_PUSH_ENABLED=true in frontend/.env.local once a real
  // Firebase project + google-services.json are in place.
  if (user?.business_id && process.env.NEXT_PUBLIC_PUSH_ENABLED === 'true') {
    registerPushNotifications()
  }
}, [user?.business_id])

  if (!isInitialized || isLoading || !user || !user.business_id) {
    return (
      <main style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p className="mono" style={{ color: 'var(--color-muted)' }}>{COPY.LOADING}</p>
      </main>
    )
  }

  const showDemoBanner =
    user.subscription_status === 'DEMO' &&
    typeof user.days_remaining === 'number' &&
    user.days_remaining <= 3

  const isExpired = user.subscription_status === 'EXPIRED'

  // Filter nav items based on role
  const visibleNavItems = NAV_ITEMS.filter(
    (item) => item.roles === null || item.roles.includes(user.role)
  )

  return (
    <div style={{ display: 'flex', minHeight: '100dvh', background: 'var(--surface-0)' }}>

      {/* Crosshair corner marks — decorative only, per LN Design System's
          "always show crosshair / grid marks" convention. Fixed positioning
          means they sit relative to the viewport regardless of scroll. */}
      <div className="crosshair ch-tl" aria-hidden="true" />
      <div className="crosshair ch-tr" aria-hidden="true" />
      <div className="crosshair ch-bl" aria-hidden="true" />
      <div className="crosshair ch-br" aria-hidden="true" />

      {/* ── Side nav (desktop, ≥768px) ── */}
      <nav style={{
        width: 200,
        flexShrink: 0,
        borderRight: '1px solid var(--surface-2)',
        background: 'var(--surface-1)',
        display: 'flex',
        flexDirection: 'column',
        padding: 'var(--sp-4) 0',
        position: 'sticky',
        top: 0,
        height: '100dvh',
        overflowY: 'auto',
      }}
        className="desktop-nav"
      >
        {/* Logo */}
        <div style={{ padding: '0 var(--sp-4) var(--sp-5)' }}>
          <div style={{ marginBottom: 'var(--sp-2)' }}>
            <Logo height={20} />
          </div>
          <span style={{ fontWeight: 700, fontSize: 'var(--fs-md)', letterSpacing: '-0.02em' }}>
            Biz<span style={{ color: 'var(--color-teal)' }}>Yangu</span>
          </span>
          {user.business_name && (
            <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user.business_name}
            </div>
          )}
        </div>

        {/* Nav links */}
        {visibleNavItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + '/')
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--sp-3)',
                padding: 'var(--sp-3) var(--sp-4)',
                color: active ? 'var(--color-teal)' : 'var(--color-muted)',
                fontWeight: active ? 600 : 400,
                fontSize: 'var(--fs-sm)',
                borderLeft: active ? '2px solid var(--color-teal)' : '2px solid transparent',
                background: active ? 'rgba(0,229,196,0.06)' : 'transparent',
                transition: 'all 0.15s',
                textDecoration: 'none',
              }}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          )
        })}

        {/* Bottom: user info */}
        <div style={{ marginTop: 'auto', padding: 'var(--sp-4)', borderTop: '1px solid var(--surface-2)' }}>
          <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 2 }}>{user.name}</div>
          <div className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--surface-4)' }}>
            {user.role}
          </div>
        </div>
      </nav>

      {/* ── Main content area ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

        {/* Demo expiry banner */}
        {showDemoBanner && (
          <div style={{
            background: 'rgba(167,139,250,0.1)',
            border: '1px solid var(--color-violet)',
            padding: 'var(--sp-2) var(--sp-4)',
            fontSize: 'var(--fs-xs)',
            color: 'var(--color-violet)',
            textAlign: 'center',
          }}>
            {COPY.DASHBOARD_DEMO_BANNER_FULL.replace('{days}', String(user.days_remaining))}
          </div>
        )}

        {/* Expired overlay */}
        {isExpired && (
          <div style={{
            background: 'rgba(255,77,109,0.08)',
            border: '1px solid var(--color-error)',
            padding: 'var(--sp-3) var(--sp-4)',
            fontSize: 'var(--fs-xs)',
            color: 'var(--color-error)',
            textAlign: 'center',
          }}>
            {COPY.DASHBOARD_EXPIRED_BANNER}
          </div>
        )}

        {children}

        {/* ── Bottom nav (mobile) ── */}
        <nav style={{
          position: 'fixed',
          bottom: 0, left: 0, right: 0,
          background: 'var(--surface-1)',
          borderTop: '1px solid var(--surface-2)',
          display: 'flex',
          zIndex: 20,
          paddingBottom: 'env(safe-area-inset-bottom)',
        }}
          className="mobile-nav"
        >
          {visibleNavItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + '/')
            return (
              <Link
                key={item.href}
                href={item.href}
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  padding: 'var(--sp-2)',
                  color: active ? 'var(--color-teal)' : 'var(--color-muted)',
                  fontSize: '9pt',
                  fontWeight: active ? 600 : 400,
                  textDecoration: 'none',
                  gap: 2,
                }}
              >
                <span style={{ fontSize: 20 }}>{item.icon}</span>
                {item.label}
              </Link>
            )
          })}
        </nav>
      </div>

      <style>{`
        @media (max-width: 767px) {
          .desktop-nav { display: none !important; }
          .mobile-nav { display: flex !important; }
          /* Add bottom padding so content isn't hidden behind mobile nav */
          main, [data-main] { padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
        }
        @media (min-width: 768px) {
          .mobile-nav { display: none !important; }
        }
      `}</style>
    </div>
  )
}
