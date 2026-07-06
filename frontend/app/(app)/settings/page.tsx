'use client'

import Link from 'next/link'
import { useAuthStore, logout, apiErrorMessage } from '@/lib/auth'
import { unregisterPushNotifications } from '@/lib/push'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { toggleTheme, getTheme } from '@/lib/theme'
import type { Theme } from '@/lib/theme'
import { COPY } from '@/lib/copy'
import {
  fetchBusiness,
  updateBusiness,
  fetchStaff,
  removeStaff,
  inviteStaff,
  type BusinessUpdatePayload,
  type InviteStaffResponse,
} from '@/lib/business'
import { shareText } from '@/lib/share-text'
import type { Business, StaffMember } from '@/lib/types'

export default function SettingsPage() {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)
  const [theme, setThemeState] = useState<Theme>('dark')
  const [mounted, setMounted] = useState(false)

  const isOwner = user?.role === 'OWNER'
  const isOwnerOrManager = user?.role === 'OWNER' || user?.role === 'MANAGER'

  useEffect(() => {
    getTheme().then(setThemeState)
    setMounted(true)
  }, [])

  async function handleToggleTheme() {
    const next = await toggleTheme()
    setThemeState(next)
  }

  async function handleLogout() {
    await unregisterPushNotifications()
    await logout()
    setUser(null)
    router.push('/login')
  }

  // ── Business profile ──────────────────────────────────────────────────────
  const [business, setBusiness] = useState<Business | null>(null)
  const [businessLoading, setBusinessLoading] = useState(true)
  const [editingBusiness, setEditingBusiness] = useState(false)
  const [businessForm, setBusinessForm] = useState<BusinessUpdatePayload>({})
  const [businessSaving, setBusinessSaving] = useState(false)
  const [businessMsg, setBusinessMsg] = useState<{ type: 'ok' | 'error'; text: string } | null>(null)

  useEffect(() => {
    fetchBusiness()
      .then(setBusiness)
      .catch(() => {})
      .finally(() => setBusinessLoading(false))
  }, [])

  function startEditingBusiness() {
    if (!business) return
    setBusinessForm({
      name: business.name,
      mpesa_till_number: business.mpesa_till_number ?? '',
      mpesa_paybill_number: business.mpesa_paybill_number ?? '',
      mpesa_business_shortcode: business.mpesa_business_shortcode ?? '',
      address: business.address ?? '',
    })
    setBusinessMsg(null)
    setEditingBusiness(true)
  }

  async function handleSaveBusiness(e: React.FormEvent) {
    e.preventDefault()
    setBusinessSaving(true)
    setBusinessMsg(null)
    try {
      const updated = await updateBusiness(businessForm)
      setBusiness(updated)
      setEditingBusiness(false)
      setBusinessMsg({ type: 'ok', text: COPY.SETTINGS_BUSINESS_UPDATED })
      // Keep the auth store's business_name in sync with the nav/header.
      if (user) setUser({ ...user, business_name: updated.name })
    } catch (err) {
      setBusinessMsg({ type: 'error', text: apiErrorMessage(err, COPY.SETTINGS_BUSINESS_UPDATE_ERROR) })
    } finally {
      setBusinessSaving(false)
    }
  }

  // ── Staff management ──────────────────────────────────────────────────────
  const [staff, setStaff] = useState<StaffMember[] | null>(null)
  const [staffLoading, setStaffLoading] = useState(false)
  const [staffError, setStaffError] = useState(false)
  const [removingId, setRemovingId] = useState<string | null>(null)

  const [inviteRole, setInviteRole] = useState<'CASHIER' | 'MANAGER'>('CASHIER')
  const [invite, setInvite] = useState<InviteStaffResponse | null>(null)
  const [inviteLoading, setInviteLoading] = useState(false)
  const [inviteError, setInviteError] = useState('')
  const [inviteCopied, setInviteCopied] = useState(false)

  useEffect(() => {
    if (!isOwnerOrManager) return
    setStaffLoading(true)
    fetchStaff()
      .then(setStaff)
      .catch(() => setStaffError(true))
      .finally(() => setStaffLoading(false))
  }, [isOwnerOrManager])

  async function handleGenerateInvite() {
    setInviteLoading(true)
    setInviteError('')
    setInvite(null)
    setInviteCopied(false)
    try {
      const result = await inviteStaff(inviteRole)
      setInvite(result)
    } catch (err) {
      setInviteError(apiErrorMessage(err, COPY.SETTINGS_INVITE_ERROR))
    } finally {
      setInviteLoading(false)
    }
  }

  async function handleCopyInvite() {
    if (!invite) return
    try {
      await navigator.clipboard.writeText(invite.invite_url)
      setInviteCopied(true)
      setTimeout(() => setInviteCopied(false), 2000)
    } catch {
      // Clipboard API unavailable — the "Share" button still works.
    }
  }

  async function handleShareInvite() {
    if (!invite) return
    await shareText(invite.invite_url)
  }

  function closeInvitePanel() {
    setInvite(null)
    setInviteError('')
  }

  async function handleRemoveStaff(member: StaffMember) {
    if (!confirm(COPY.SETTINGS_STAFF_REMOVE_CONFIRM.replace('{name}', member.name))) return
    setRemovingId(member.id)
    try {
      await removeStaff(member.id)
      setStaff((prev) => (prev ? prev.filter((s) => s.id !== member.id) : prev))
    } catch (err) {
      alert(apiErrorMessage(err, COPY.SETTINGS_STAFF_REMOVE_ERROR))
    } finally {
      setRemovingId(null)
    }
  }

  return (
    <main style={{ padding: 'var(--sp-6) var(--sp-5)', maxWidth: 720 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-6)' }}>
        <h1 style={{ fontSize: 'var(--fs-lg)' }}>{COPY.SETTINGS_TITLE}</h1>
        <Link href="/dashboard" className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_GO_HOME}</Link>
      </div>

      {/* User info */}
      <div className="card" style={{ marginBottom: 'var(--sp-4)' }}>
        <p className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>{COPY.SETTINGS_ACCOUNT_LABEL}</p>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--sp-1)' }}>
          <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_NAME}</span>
          <span style={{ fontSize: 'var(--fs-xs)' }}>{user?.name}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--sp-1)' }}>
          <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_PHONE}</span>
          <span className="mono" style={{ fontSize: 'var(--fs-xs)' }}>{user?.phone_number}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_ROLE}</span>
          <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-teal)' }}>{user?.role}</span>
        </div>
      </div>

      {/* Business info */}
      <div className="card" style={{ marginBottom: 'var(--sp-4)' }}>
        <p className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>{COPY.SETTINGS_BUSINESS_LABEL}</p>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--sp-1)' }}>
          <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_BUSINESS_NAME}</span>
          <span style={{ fontSize: 'var(--fs-xs)' }}>{user?.business_name}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_BUSINESS_STATUS}</span>
          <span
            className={`badge ${
              user?.subscription_status === 'ACTIVE' ? 'badge-active'
              : user?.subscription_status === 'DEMO' ? 'badge-demo'
              : user?.subscription_status === 'EXPIRED' ? 'badge-expired'
              : user?.subscription_status === 'SUSPENDED' ? 'badge-suspended'
              : 'badge-muted'
            }`}
            style={{ fontSize: 'var(--fs-xs)' }}
          >
            {user?.subscription_status === 'DEMO'
              ? COPY.SETTINGS_DEMO_DAYS_REMAINING.replace('{days}', String(user.days_remaining))
              : user?.subscription_status}
          </span>
        </div>
      </div>

      {/* Business profile edit — owner only */}
      <div className="card" style={{ marginBottom: 'var(--sp-4)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-2)' }}>
          <p className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.SETTINGS_BUSINESS_PROFILE_TITLE}</p>
          {isOwner && !editingBusiness && business && (
            <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }} onClick={startEditingBusiness}>
              {COPY.SETTINGS_EDIT}
            </button>
          )}
        </div>

        {businessLoading && <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.LOADING}</p>}

        {!businessLoading && business && !editingBusiness && (
          <>
            <ProfileRow label={COPY.SETTINGS_MPESA_TILL} value={business.mpesa_till_number} />
            <ProfileRow label={COPY.SETTINGS_MPESA_PAYBILL} value={business.mpesa_paybill_number} />
            <ProfileRow label={COPY.SETTINGS_MPESA_SHORTCODE} value={business.mpesa_business_shortcode} />
            <ProfileRow label={COPY.SETTINGS_ADDRESS} value={business.address} last />
            {!isOwner && (
              <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginTop: 'var(--sp-2)' }}>
                {COPY.SETTINGS_OWNER_ONLY_EDIT}
              </p>
            )}
          </>
        )}

        {editingBusiness && business && (
          <form onSubmit={handleSaveBusiness}>
            <label className="mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
              {COPY.SETTINGS_BUSINESS_NAME}
            </label>
            <input
              className="input"
              style={{ marginBottom: 'var(--sp-3)' }}
              value={businessForm.name ?? ''}
              onChange={(e) => setBusinessForm((f) => ({ ...f, name: e.target.value }))}
              required
            />
            <label className="mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
              {COPY.SETTINGS_MPESA_TILL}
            </label>
            <input
              className="input mono"
              style={{ marginBottom: 'var(--sp-3)' }}
              value={businessForm.mpesa_till_number ?? ''}
              onChange={(e) => setBusinessForm((f) => ({ ...f, mpesa_till_number: e.target.value }))}
            />
            <label className="mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
              {COPY.SETTINGS_MPESA_PAYBILL}
            </label>
            <input
              className="input mono"
              style={{ marginBottom: 'var(--sp-3)' }}
              value={businessForm.mpesa_paybill_number ?? ''}
              onChange={(e) => setBusinessForm((f) => ({ ...f, mpesa_paybill_number: e.target.value }))}
            />
            <label className="mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
              {COPY.SETTINGS_MPESA_SHORTCODE}
            </label>
            <input
              className="input mono"
              style={{ marginBottom: 'var(--sp-3)' }}
              value={businessForm.mpesa_business_shortcode ?? ''}
              onChange={(e) => setBusinessForm((f) => ({ ...f, mpesa_business_shortcode: e.target.value }))}
            />
            <label className="mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
              {COPY.SETTINGS_ADDRESS}
            </label>
            <input
              className="input"
              style={{ marginBottom: 'var(--sp-4)' }}
              value={businessForm.address ?? ''}
              onChange={(e) => setBusinessForm((f) => ({ ...f, address: e.target.value }))}
            />
            <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
              <button type="submit" className="btn-primary" disabled={businessSaving} style={{ flex: 1, justifyContent: 'center' }}>
                {businessSaving ? '…' : COPY.SAVE}
              </button>
              <button type="button" className="btn-ghost" onClick={() => setEditingBusiness(false)} style={{ flex: 1, justifyContent: 'center' }}>
                {COPY.CANCEL}
              </button>
            </div>
          </form>
        )}

        {businessMsg && (
          <p style={{ fontSize: 'var(--fs-xs)', marginTop: 'var(--sp-3)', color: businessMsg.type === 'ok' ? 'var(--color-teal)' : 'var(--color-error)' }}>
            {businessMsg.text}
          </p>
        )}
      </div>

      {/* Staff management — owner/manager only */}
      {isOwnerOrManager && (
        <div className="card" style={{ marginBottom: 'var(--sp-4)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-3)' }}>
            <p className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
              {COPY.SETTINGS_STAFF_TITLE}
              {staff && (
                <span style={{ marginLeft: 'var(--sp-2)', color: 'var(--color-off-white)' }}>
                  · {staff.length === 1 ? COPY.SETTINGS_STAFF_COUNT_ONE : COPY.SETTINGS_STAFF_COUNT_MANY.replace('{count}', String(staff.length))}
                </span>
              )}
            </p>
            {isOwner && !invite && (
              <button
                className="btn-ghost"
                style={{ fontSize: 'var(--fs-xs)' }}
                onClick={() => { setInvite(null); setInviteError(''); document.getElementById('invite-panel')?.scrollIntoView({ behavior: 'smooth' }) }}
              >
                {COPY.SETTINGS_INVITE_STAFF}
              </button>
            )}
          </div>

          {staffLoading && <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.SETTINGS_STAFF_LOADING}</p>}
          {!staffLoading && staffError && <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-error)' }}>{COPY.SETTINGS_STAFF_ERROR}</p>}

          {!staffLoading && !staffError && staff && staff.length === 0 && (
            <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.SETTINGS_STAFF_EMPTY}</p>
          )}

          {!staffLoading && !staffError && staff && staff.length > 0 && (
            <div style={{ marginBottom: isOwner ? 'var(--sp-4)' : 0 }}>
              {staff.map((member) => (
                <div
                  key={member.id}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: 'var(--sp-2) 0', borderBottom: '1px solid var(--color-border)',
                  }}
                >
                  <div>
                    <div style={{ fontSize: 'var(--fs-sm)' }}>
                      {member.name}
                      {member.id === user?.id && (
                        <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}> ({COPY.SETTINGS_STAFF_YOU})</span>
                      )}
                    </div>
                    <div className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>
                      {member.phone_number} · {member.role}
                    </div>
                  </div>
                  {isOwner && member.id !== user?.id && (
                    <button
                      className="btn-ghost"
                      style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-error)' }}
                      disabled={removingId === member.id}
                      onClick={() => handleRemoveStaff(member)}
                    >
                      {removingId === member.id ? '…' : COPY.SETTINGS_STAFF_REMOVE}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {!isOwner && (
            <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginTop: 'var(--sp-2)' }}>{COPY.SETTINGS_STAFF_OWNER_ONLY}</p>
          )}

          {/* Invite panel — owner only */}
          {isOwner && (
            <div id="invite-panel">
              {!invite && (
                <div style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 140 }}>
                    <label className="mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
                      {COPY.SETTINGS_INVITE_ROLE_LABEL}
                    </label>
                    <select
                      className="input"
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value as 'CASHIER' | 'MANAGER')}
                    >
                      <option value="CASHIER">{COPY.SETTINGS_INVITE_CASHIER}</option>
                      <option value="MANAGER">{COPY.SETTINGS_INVITE_MANAGER}</option>
                    </select>
                  </div>
                  <button className="btn-primary" disabled={inviteLoading} onClick={handleGenerateInvite}>
                    {inviteLoading ? COPY.SETTINGS_INVITE_GENERATING : COPY.SETTINGS_INVITE_GENERATE}
                  </button>
                </div>
              )}

              {inviteError && <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-error)', marginTop: 'var(--sp-2)' }}>{inviteError}</p>}

              {invite && (
                <div className="card-terminal" style={{ padding: 'var(--sp-3)', marginTop: 'var(--sp-2)' }}>
                  <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>
                    {COPY.SETTINGS_INVITE_LINK_READY}
                  </p>
                  <p className="mono" style={{ fontSize: 'var(--fs-xs)', wordBreak: 'break-all', color: 'var(--color-teal)', marginBottom: 'var(--sp-3)' }}>
                    {invite.invite_url}
                  </p>
                  <div style={{ display: 'flex', gap: 'var(--sp-2)', flexWrap: 'wrap' }}>
                    <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }} onClick={handleCopyInvite}>
                      {inviteCopied ? COPY.SETTINGS_INVITE_COPIED : COPY.SETTINGS_INVITE_COPY}
                    </button>
                    <button className="btn-primary" style={{ fontSize: 'var(--fs-xs)' }} onClick={handleShareInvite}>
                      {COPY.SETTINGS_INVITE_SHARE_WHATSAPP}
                    </button>
                    <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }} onClick={closeInvitePanel}>
                      {COPY.SETTINGS_INVITE_DONE}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Theme toggle */}
      <div className="card" style={{ marginBottom: 'var(--sp-4)' }}>
        <p className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>{COPY.SETTINGS_THEME_LABEL}</p>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_THEME}</span>
          {mounted && (
            <button
              className="theme-toggle"
              onClick={handleToggleTheme}
              style={{
                cursor: 'pointer',
                padding: 'var(--sp-2) var(--sp-3)',
                fontSize: 'var(--fs-sm)',
              }}
            >
              {theme === 'dark' ? COPY.SETTINGS_THEME_LIGHT : COPY.SETTINGS_THEME_DARK}
            </button>
          )}
        </div>
      </div>

      {/* Coming soon */}
      <div className="card-terminal" style={{ padding: 'var(--sp-4)', marginBottom: 'var(--sp-5)' }}>
        <p className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-teal)', marginBottom: 'var(--sp-2)' }}>
          {COPY.SETTINGS_FUTURE_FEATURES}
        </p>
        <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)', lineHeight: 1.8 }}>
          {COPY.SETTINGS_FUTURE_FEATURES_ITEMS.map((item) => (
            <span key={item}>• {item}<br /></span>
          ))}
        </p>
      </div>

      <button className="btn-destructive" onClick={handleLogout} style={{ width: '100%' }}>
        {COPY.SETTINGS_LOGOUT}
      </button>
    </main>
  )
}

function ProfileRow({ label, value, last }: { label: string; value: string | null; last?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: last ? 0 : 'var(--sp-1)' }}>
      <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{label}</span>
      <span className="mono" style={{ fontSize: 'var(--fs-xs)' }}>{value || '—'}</span>
    </div>
  )
}
