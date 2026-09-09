'use client'

import Link from 'next/link'
import { useAuthStore, logout, apiErrorMessage, updateMe, fetchMe, type UpdateMePayload } from '@/lib/auth'
import { unregisterPushNotifications } from '@/lib/push'
import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useRef, useState } from 'react'
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
import { isPinEnabledOnDevice, setPinEnabledOnDevice } from '@/lib/device-lock'
import { isBiometricAvailable, isBiometricEnabled, disableBiometric } from '@/lib/biometric'
import {
  fetchBusinessMpesaCredentials,
  saveBusinessMpesaCredentials,
  verifyBusinessMpesaCredentials,
  deactivateBusinessMpesaCredentials,
  initiateSubscriptionPayment,
  pollSubscriptionPaymentStatus,
  type BusinessMpesaCredentialsPayload,
} from '@/lib/payments'
import type {
  Business, StaffMember, MpesaWsEvent, SubscriptionPayment,
  BusinessMpesaCredentials as BusinessMpesaCredentialsType,
} from '@/lib/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'
const WS_BASE = API_BASE.replace(/^http/, 'ws').replace('/api/v1', '')

// ── Subscription payment modal ──────────────────────────────────────────────
// Deliberately NO manual-reference-entry fallback like the sale flow's
// StkWaitingScreen has — this is a business paying BizYangu, so letting
// someone self-declare "I paid" with a typed-in code (unverified against
// Daraja) would let a business unlock ACTIVE status without actually
// paying. If the callback/poll never resolves, they wait or try again —
// see MPESA_CONFIG_CHANGES.md for why this is scoped tighter than sales.

type SubStep = 'form' | 'waiting' | 'confirmed' | 'failed'

function SubscriptionPaymentModal({
  businessId,
  defaultPhone,
  onClose,
  onConfirmed,
}: {
  businessId: string
  defaultPhone: string
  onClose: () => void
  onConfirmed: () => void
}) {
  const [step, setStep] = useState<SubStep>('form')
  const [phone, setPhone] = useState(defaultPhone)
  const [amount, setAmount] = useState('800')
  const [months, setMonths] = useState('1')
  const [payment, setPayment] = useState<SubscriptionPayment | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [dotCount, setDotCount] = useState(1)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (step !== 'waiting') return
    const t = setInterval(() => setDotCount((d) => (d % 3) + 1), 600)
    return () => clearInterval(t)
  }, [step])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const result = await initiateSubscriptionPayment({
        phone_number: phone.trim(),
        amount: Number(amount),
        months: Number(months) || 1,
      })
      setPayment(result)
      setStep('waiting')
    } catch (err) {
      setError(apiErrorMessage(err, COPY.SETTINGS_SUB_SEND_ERROR))
    } finally {
      setSubmitting(false)
    }
  }

  const handleWsMessage = useCallback((event: MessageEvent) => {
    try {
      const msg: MpesaWsEvent = JSON.parse(event.data)
      if (msg.type === 'subscription_result' && msg.checkout_request_id === payment?.checkout_request_id) {
        if (msg.status === 'CONFIRMED') {
          wsRef.current?.close()
          setStep('confirmed')
          onConfirmed()
        } else if (msg.status === 'FAILED' || msg.status === 'CANCELLED') {
          setStep('failed')
        }
      }
    } catch {
      // malformed message — ignore, polling is the fallback
    }
  }, [payment?.checkout_request_id, onConfirmed])

  useEffect(() => {
    if (step !== 'waiting') return
    const wsUrl = `${WS_BASE}/ws/mpesa/${businessId}/`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    ws.onmessage = handleWsMessage
    ws.onerror = () => {} // silent — polling is fallback
    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [step, businessId, handleWsMessage])

  // Polling fallback every 5s
  useEffect(() => {
    if (step !== 'waiting' || !payment) return
    const interval = setInterval(async () => {
      try {
        const result = await pollSubscriptionPaymentStatus(payment.checkout_request_id)
        if (result.status === 'CONFIRMED') {
          setStep('confirmed')
          onConfirmed()
        } else if (result.status === 'FAILED' || result.status === 'CANCELLED') {
          setStep('failed')
        }
      } catch {
        // silent — WS is the primary path
      }
    }, 5000)
    return () => clearInterval(interval)
  }, [step, payment, onConfirmed])

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 50,
      background: 'rgba(0,0,0,0.85)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 'var(--sp-5)',
    }}>
      <div className="card" style={{ maxWidth: 380, width: '100%', textAlign: 'center' }}>

        {step === 'form' && (
          <form onSubmit={handleSubmit}>
            <h2 style={{ fontSize: 'var(--fs-md)', marginBottom: 'var(--sp-4)' }}>{COPY.SETTINGS_SUB_MODAL_TITLE}</h2>
            <label className="mono" style={{ display: 'block', textAlign: 'left', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
              {COPY.SETTINGS_SUB_PHONE_LABEL}
            </label>
            <input
              className="input mono"
              style={{ marginBottom: 'var(--sp-3)' }}
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="0712345678"
              required
            />
            <label className="mono" style={{ display: 'block', textAlign: 'left', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
              {COPY.SETTINGS_SUB_AMOUNT_LABEL}
            </label>
            <input
              className="input mono"
              type="number"
              min="1"
              style={{ marginBottom: 'var(--sp-3)' }}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
            />
            <label className="mono" style={{ display: 'block', textAlign: 'left', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
              {COPY.SETTINGS_SUB_MONTHS_LABEL}
            </label>
            <input
              className="input mono"
              type="number"
              min="1"
              style={{ marginBottom: 'var(--sp-4)' }}
              value={months}
              onChange={(e) => setMonths(e.target.value)}
              required
            />
            {error && (
              <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-error)', marginBottom: 'var(--sp-3)' }}>{error}</p>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
              <button type="submit" className="btn-primary" disabled={submitting}>
                {submitting ? '…' : COPY.SETTINGS_SUB_SEND}
              </button>
              <button type="button" className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }} onClick={onClose}>
                {COPY.CANCEL}
              </button>
            </div>
          </form>
        )}

        {step === 'waiting' && (
          <>
            <div style={{ marginBottom: 'var(--sp-5)' }}>
              <div style={{
                width: 64, height: 64, borderRadius: '50%',
                border: '3px solid var(--surface-3)',
                borderTopColor: 'var(--color-teal)',
                margin: '0 auto',
                animation: 'byz-spin 1s linear infinite',
              }} />
            </div>
            <h2 style={{ fontSize: 'var(--fs-md)', marginBottom: 'var(--sp-2)' }}>
              {COPY.SETTINGS_SUB_WAITING_TITLE}{'.'.repeat(dotCount)}
            </h2>
            <p style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-1)' }}>
              {COPY.SETTINGS_SUB_SENT_TO}
            </p>
            <p className="mono" style={{ color: 'var(--color-teal)', fontSize: 'var(--fs-sm)', marginBottom: 'var(--sp-5)' }}>
              {phone}
            </p>
            <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-error)' }} onClick={onClose}>
              {COPY.SETTINGS_SUB_CLOSE}
            </button>
          </>
        )}

        {step === 'confirmed' && (
          <>
            <div style={{ fontSize: 40, marginBottom: 'var(--sp-3)' }}>✅</div>
            <h2 style={{ fontSize: 'var(--fs-md)', marginBottom: 'var(--sp-2)' }}>{COPY.SETTINGS_SUB_CONFIRMED}</h2>
            <button className="btn-primary" style={{ marginTop: 'var(--sp-3)' }} onClick={onClose}>
              {COPY.SETTINGS_SUB_CLOSE}
            </button>
          </>
        )}

        {step === 'failed' && (
          <>
            <div style={{ fontSize: 40, marginBottom: 'var(--sp-3)' }}>⚠️</div>
            <h2 style={{ fontSize: 'var(--fs-md)', marginBottom: 'var(--sp-2)' }}>{COPY.SETTINGS_SUB_FAILED}</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)', marginTop: 'var(--sp-3)' }}>
              <button className="btn-primary" onClick={() => { setStep('form'); setError('') }}>
                {COPY.SETTINGS_SUB_TRY_AGAIN}
              </button>
              <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }} onClick={onClose}>
                {COPY.SETTINGS_SUB_CLOSE}
              </button>
            </div>
          </>
        )}
      </div>

      <style>{`
        @keyframes byz-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

export default function SettingsPage() {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)
  const [theme, setThemeState] = useState<Theme>('dark')
  const [mounted, setMounted] = useState(false)

  const isOwner = user?.role === 'OWNER'
  const isOwnerOrManager = user?.role === 'OWNER' || user?.role === 'MANAGER'

  // ── Subscription payment (owner only) ───────────────────────────────────
  const [showSubModal, setShowSubModal] = useState(false)

  // ── Account details (name/email) ────────────────────────────────────────
  // Previously nothing here beyond a read-only name/phone/role — first/last
  // name and email weren't even fields on the account, so there was nothing
  // to edit. Anyone can edit their own name; email is really only meaningful
  // for the OWNER (collected on /setup) but any role can add one.
  const [editingAccount, setEditingAccount] = useState(false)
  const [accountForm, setAccountForm] = useState<UpdateMePayload>({})
  const [accountSaving, setAccountSaving] = useState(false)
  const [accountMsg, setAccountMsg] = useState<{ type: 'ok' | 'error'; text: string } | null>(null)

  function startEditingAccount() {
    if (!user) return
    setAccountForm({
      first_name: user.first_name ?? '',
      last_name: user.last_name ?? '',
      email: user.email ?? '',
    })
    setAccountMsg(null)
    setEditingAccount(true)
  }

  async function handleSaveAccount(e: React.FormEvent) {
    e.preventDefault()
    if (!accountForm.first_name?.trim()) {
      setAccountMsg({ type: 'error', text: COPY.ERRORS.FIRST_NAME_REQUIRED })
      return
    }
    if (!accountForm.last_name?.trim()) {
      setAccountMsg({ type: 'error', text: COPY.ERRORS.LAST_NAME_REQUIRED })
      return
    }
    setAccountSaving(true)
    setAccountMsg(null)
    try {
      const updated = await updateMe({
        first_name: accountForm.first_name?.trim(),
        last_name: accountForm.last_name?.trim(),
        email: accountForm.email?.trim() ? accountForm.email.trim() : null,
      })
      setUser(updated)
      setEditingAccount(false)
      setAccountMsg({ type: 'ok', text: COPY.SETTINGS_ACCOUNT_UPDATED })
    } catch (err) {
      setAccountMsg({ type: 'error', text: apiErrorMessage(err, COPY.SETTINGS_ACCOUNT_UPDATE_ERROR) })
    } finally {
      setAccountSaving(false)
    }
  }

  useEffect(() => {
    getTheme().then(setThemeState)
    setMounted(true)
  }, [])

  async function handleToggleTheme() {
    const next = await toggleTheme()
    setThemeState(next)
  }

  // ── Security (PIN + biometric) ──────────────────────────────────────────
  const [pinEnabled, setPinEnabledState] = useState(false)
  const [biometricHardwareAvailable, setBiometricHardwareAvailable] = useState(false)
  const [biometricOn, setBiometricOn] = useState(false)

  useEffect(() => {
    isPinEnabledOnDevice().then(setPinEnabledState)
    isBiometricAvailable().then(setBiometricHardwareAvailable)
    isBiometricEnabled().then(setBiometricOn)
  }, [])

  async function handleTurnOffPin() {
    await disableBiometric()
    await setPinEnabledOnDevice(false)
    setPinEnabledState(false)
    setBiometricOn(false)
  }

  async function handleTurnOffBiometric() {
    await disableBiometric()
    setBiometricOn(false)
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

  // ── Business's own M-Pesa till (owner only) ─────────────────────────────────
  const [mpesaCreds, setMpesaCreds] = useState<BusinessMpesaCredentialsType | null>(null)
  const [mpesaLoading, setMpesaLoading] = useState(false)
  const [editingMpesa, setEditingMpesa] = useState(false)
  const [mpesaForm, setMpesaForm] = useState<BusinessMpesaCredentialsPayload>({})
  const [mpesaSaving, setMpesaSaving] = useState(false)
  const [mpesaVerifying, setMpesaVerifying] = useState(false)
  const [mpesaMsg, setMpesaMsg] = useState<{ type: 'ok' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (!isOwner) return
    setMpesaLoading(true)
    fetchBusinessMpesaCredentials()
      .then(setMpesaCreds)
      .catch(() => {})
      .finally(() => setMpesaLoading(false))
  }, [isOwner])

  function startEditingMpesa() {
    if (!mpesaCreds) return
    setMpesaForm({
      till_type: mpesaCreds.till_type,
      shortcode: mpesaCreds.shortcode ?? '',
      consumer_key: '',
      consumer_secret: '',
      passkey: '',
      env: mpesaCreds.env,
    })
    setMpesaMsg(null)
    setEditingMpesa(true)
  }

  async function handleSaveMpesa(e: React.FormEvent) {
    e.preventDefault()
    setMpesaSaving(true)
    setMpesaMsg(null)
    try {
      const updated = await saveBusinessMpesaCredentials(mpesaForm)
      setMpesaCreds(updated)
      setEditingMpesa(false)
      setMpesaMsg({ type: 'ok', text: updated.detail || COPY.SETTINGS_BUSINESS_UPDATED })
    } catch (err) {
      setMpesaMsg({ type: 'error', text: apiErrorMessage(err, COPY.SETTINGS_MPESA_SAVE_ERROR) })
    } finally {
      setMpesaSaving(false)
    }
  }

  async function handleVerifyMpesa() {
    setMpesaVerifying(true)
    setMpesaMsg(null)
    try {
      const updated = await verifyBusinessMpesaCredentials()
      setMpesaCreds(updated)
      setMpesaMsg({ type: 'ok', text: updated.detail || COPY.SETTINGS_BUSINESS_UPDATED })
    } catch (err) {
      setMpesaMsg({ type: 'error', text: apiErrorMessage(err, COPY.SETTINGS_MPESA_VERIFY_ERROR) })
    } finally {
      setMpesaVerifying(false)
    }
  }

  async function handleDeactivateMpesa() {
    if (!confirm(COPY.SETTINGS_MPESA_DEACTIVATE_CONFIRM)) return
    setMpesaMsg(null)
    try {
      const updated = await deactivateBusinessMpesaCredentials()
      setMpesaCreds(updated)
      setMpesaMsg({ type: 'ok', text: updated.detail || COPY.SETTINGS_BUSINESS_UPDATED })
    } catch (err) {
      setMpesaMsg({ type: 'error', text: apiErrorMessage(err, COPY.SETTINGS_MPESA_SAVE_ERROR) })
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-2)' }}>
          <p className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.SETTINGS_ACCOUNT_LABEL}</p>
          {!editingAccount && (
            <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }} onClick={startEditingAccount}>
              {COPY.SETTINGS_EDIT_ACCOUNT}
            </button>
          )}
        </div>

        {editingAccount ? (
          <form onSubmit={handleSaveAccount}>
            <label style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>{COPY.SETUP_FIRST_NAME_LABEL}</label>
            <input
              className="input"
              value={accountForm.first_name ?? ''}
              onChange={(e) => setAccountForm({ ...accountForm, first_name: e.target.value })}
              style={{ marginBottom: 'var(--sp-3)' }}
              required
            />
            <label style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>{COPY.SETUP_LAST_NAME_LABEL}</label>
            <input
              className="input"
              value={accountForm.last_name ?? ''}
              onChange={(e) => setAccountForm({ ...accountForm, last_name: e.target.value })}
              style={{ marginBottom: 'var(--sp-3)' }}
              required
            />
            <label style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>{COPY.SETTINGS_EMAIL}</label>
            <input
              className="input"
              type="email"
              value={accountForm.email ?? ''}
              onChange={(e) => setAccountForm({ ...accountForm, email: e.target.value })}
              style={{ marginBottom: 'var(--sp-3)' }}
            />
            {accountMsg && (
              <p style={{ fontSize: 'var(--fs-xs)', color: accountMsg.type === 'ok' ? 'var(--color-teal)' : 'var(--color-error)', marginBottom: 'var(--sp-3)' }}>
                {accountMsg.text}
              </p>
            )}
            <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
              <button type="submit" className="btn-primary" disabled={accountSaving} style={{ fontSize: 'var(--fs-xs)' }}>
                {accountSaving ? COPY.SETTINGS_ACCOUNT_SAVING : COPY.SETTINGS_ACCOUNT_SAVE}
              </button>
              <button type="button" className="btn-ghost" disabled={accountSaving} style={{ fontSize: 'var(--fs-xs)' }} onClick={() => setEditingAccount(false)}>
                {COPY.SETTINGS_ACCOUNT_CANCEL}
              </button>
            </div>
          </form>
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--sp-1)' }}>
              <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_NAME}</span>
              <span style={{ fontSize: 'var(--fs-xs)' }}>{user?.name || COPY.SETTINGS_NAME_NOT_SET}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--sp-1)' }}>
              <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_EMAIL}</span>
              <span className="mono" style={{ fontSize: 'var(--fs-xs)' }}>{user?.email || COPY.SETTINGS_EMAIL_NOT_SET}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--sp-1)' }}>
              <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_PHONE}</span>
              <span className="mono" style={{ fontSize: 'var(--fs-xs)' }}>{user?.phone_number}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_ROLE}</span>
              <span className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-teal)' }}>{user?.role}</span>
            </div>
          </>
        )}
      </div>

      {/* Business info */}
      <div className="card" style={{ marginBottom: 'var(--sp-4)' }}>
        <p className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-2)' }}>{COPY.SETTINGS_BUSINESS_LABEL}</p>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--sp-1)' }}>
          <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_BUSINESS_NAME}</span>
          <span style={{ fontSize: 'var(--fs-xs)' }}>{user?.business_name}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: isOwner && user?.subscription_status !== 'ACTIVE' ? 'var(--sp-3)' : 0 }}>
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
        {isOwner && user?.subscription_status !== 'ACTIVE' && (
          <button className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={() => setShowSubModal(true)}>
            {COPY.SETTINGS_PAY_SUBSCRIPTION}
          </button>
        )}
      </div>

      {showSubModal && user?.business_id && (
        <SubscriptionPaymentModal
          businessId={user.business_id}
          defaultPhone={user.phone_number ?? ''}
          onClose={() => setShowSubModal(false)}
          onConfirmed={() => {
            fetchMe().then(setUser).catch(() => {})
          }}
        />
      )}

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

      {/* Business's own M-Pesa till — owner only */}
      {isOwner && (
        <div className="card" style={{ marginBottom: 'var(--sp-4)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-1)' }}>
            <p className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.SETTINGS_MPESA_OWN_TITLE}</p>
            {!editingMpesa && mpesaCreds && (
              <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }} onClick={startEditingMpesa}>
                {COPY.SETTINGS_EDIT}
              </button>
            )}
          </div>
          <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-3)' }}>
            {COPY.SETTINGS_MPESA_OWN_SUBTITLE}
          </p>

          {mpesaLoading && <p style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)' }}>{COPY.LOADING}</p>}

          {!mpesaLoading && mpesaCreds && !editingMpesa && (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--sp-2)' }}>
                <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>{COPY.SETTINGS_BUSINESS_STATUS}</span>
                <span
                  className={`badge ${mpesaCreds.is_active ? 'badge-active' : mpesaCreds.is_configured ? 'badge-demo' : 'badge-muted'}`}
                  style={{ fontSize: 'var(--fs-xs)' }}
                >
                  {mpesaCreds.is_active
                    ? COPY.SETTINGS_MPESA_OWN_STATUS_ACTIVE
                    : mpesaCreds.is_configured
                    ? COPY.SETTINGS_MPESA_OWN_STATUS_UNVERIFIED
                    : COPY.SETTINGS_MPESA_OWN_STATUS_NOT_SET}
                </span>
              </div>
              <ProfileRow
                label={COPY.SETTINGS_MPESA_TILL_TYPE}
                value={mpesaCreds.till_type === 'BUY_GOODS' ? COPY.SETTINGS_MPESA_TILL_TYPE_BUY_GOODS : COPY.SETTINGS_MPESA_TILL_TYPE_PAYBILL}
              />
              <ProfileRow label={COPY.SETTINGS_MPESA_OWN_SHORTCODE} value={mpesaCreds.shortcode} />
              <ProfileRow label={COPY.SETTINGS_MPESA_CONSUMER_KEY} value={mpesaCreds.consumer_key_masked} last={!mpesaCreds.is_configured} />

              {mpesaCreds.is_configured && (
                <div style={{ display: 'flex', gap: 'var(--sp-2)', marginTop: 'var(--sp-3)' }}>
                  {!mpesaCreds.is_active && (
                    <button className="btn-primary" style={{ fontSize: 'var(--fs-xs)' }} disabled={mpesaVerifying} onClick={handleVerifyMpesa}>
                      {mpesaVerifying ? COPY.SETTINGS_MPESA_VERIFYING : COPY.SETTINGS_MPESA_VERIFY}
                    </button>
                  )}
                  {mpesaCreds.is_active && (
                    <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-error)' }} onClick={handleDeactivateMpesa}>
                      {COPY.SETTINGS_MPESA_DEACTIVATE}
                    </button>
                  )}
                </div>
              )}
            </>
          )}

          {editingMpesa && (
            <form onSubmit={handleSaveMpesa}>
              <label className="mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
                {COPY.SETTINGS_MPESA_TILL_TYPE}
              </label>
              <select
                className="input"
                style={{ marginBottom: 'var(--sp-3)' }}
                value={mpesaForm.till_type ?? 'PAYBILL'}
                onChange={(e) => setMpesaForm((f) => ({ ...f, till_type: e.target.value as 'PAYBILL' | 'BUY_GOODS' }))}
              >
                <option value="PAYBILL">{COPY.SETTINGS_MPESA_TILL_TYPE_PAYBILL}</option>
                <option value="BUY_GOODS">{COPY.SETTINGS_MPESA_TILL_TYPE_BUY_GOODS}</option>
              </select>

              <label className="mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
                {COPY.SETTINGS_MPESA_OWN_SHORTCODE}
              </label>
              <input
                className="input mono"
                style={{ marginBottom: 'var(--sp-3)' }}
                value={mpesaForm.shortcode ?? ''}
                onChange={(e) => setMpesaForm((f) => ({ ...f, shortcode: e.target.value }))}
              />

              <label className="mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
                {COPY.SETTINGS_MPESA_CONSUMER_KEY}
              </label>
              <input
                className="input mono"
                style={{ marginBottom: 'var(--sp-3)' }}
                value={mpesaForm.consumer_key ?? ''}
                onChange={(e) => setMpesaForm((f) => ({ ...f, consumer_key: e.target.value }))}
              />

              <label className="mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
                {COPY.SETTINGS_MPESA_CONSUMER_SECRET}
              </label>
              <input
                className="input mono"
                type="password"
                placeholder={COPY.SETTINGS_MPESA_CONSUMER_SECRET_HINT}
                style={{ marginBottom: 'var(--sp-3)' }}
                value={mpesaForm.consumer_secret ?? ''}
                onChange={(e) => setMpesaForm((f) => ({ ...f, consumer_secret: e.target.value }))}
              />

              <label className="mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
                {COPY.SETTINGS_MPESA_PASSKEY}
              </label>
              <input
                className="input mono"
                type="password"
                placeholder={COPY.SETTINGS_MPESA_PASSKEY_HINT}
                style={{ marginBottom: 'var(--sp-3)' }}
                value={mpesaForm.passkey ?? ''}
                onChange={(e) => setMpesaForm((f) => ({ ...f, passkey: e.target.value }))}
              />

              <label className="mono" style={{ display: 'block', fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-1)' }}>
                {COPY.SETTINGS_MPESA_ENV}
              </label>
              <select
                className="input"
                style={{ marginBottom: 'var(--sp-4)' }}
                value={mpesaForm.env ?? 'sandbox'}
                onChange={(e) => setMpesaForm((f) => ({ ...f, env: e.target.value as 'sandbox' | 'production' }))}
              >
                <option value="sandbox">{COPY.SETTINGS_MPESA_ENV_SANDBOX}</option>
                <option value="production">{COPY.SETTINGS_MPESA_ENV_PRODUCTION}</option>
              </select>

              <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
                <button type="submit" className="btn-primary" disabled={mpesaSaving} style={{ flex: 1, justifyContent: 'center' }}>
                  {mpesaSaving ? '…' : COPY.SAVE}
                </button>
                <button type="button" className="btn-ghost" onClick={() => setEditingMpesa(false)} style={{ flex: 1, justifyContent: 'center' }}>
                  {COPY.CANCEL}
                </button>
              </div>
            </form>
          )}

          {!mpesaLoading && !mpesaCreds && !editingMpesa && (
            <button
              className="btn-secondary"
              style={{ fontSize: 'var(--fs-xs)' }}
              onClick={() => { setMpesaForm({ till_type: 'PAYBILL', env: 'sandbox' }); setMpesaMsg(null); setEditingMpesa(true) }}
            >
              {COPY.SETTINGS_EDIT}
            </button>
          )}

          {mpesaMsg && (
            <p style={{ fontSize: 'var(--fs-xs)', marginTop: 'var(--sp-3)', color: mpesaMsg.type === 'ok' ? 'var(--color-teal)' : 'var(--color-error)' }}>
              {mpesaMsg.text}
            </p>
          )}
        </div>
      )}

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

      {/* Security: PIN + biometric */}
      <div className="card" style={{ marginBottom: 'var(--sp-4)' }}>
        <p className="mono" style={{ fontSize: 'var(--fs-xs)', color: 'var(--color-muted)', marginBottom: 'var(--sp-3)' }}>
          {COPY.SETTINGS_SECURITY_TITLE}
        </p>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-3)' }}>
          <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>
            {pinEnabled ? COPY.SETTINGS_SECURITY_PIN_ON : COPY.SETTINGS_SECURITY_PIN_OFF}
          </span>
          {pinEnabled ? (
            <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
              <Link href="/pin/setup" className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }}>
                {COPY.SETTINGS_SECURITY_CHANGE_PIN}
              </Link>
              <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }} onClick={handleTurnOffPin}>
                {COPY.SETTINGS_SECURITY_TURN_OFF}
              </button>
            </div>
          ) : (
            <Link href="/pin/setup" className="btn-secondary" style={{ fontSize: 'var(--fs-xs)' }}>
              {COPY.SETTINGS_SECURITY_SET_PIN}
            </Link>
          )}
        </div>

        {pinEnabled && biometricHardwareAvailable && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--color-muted)', fontSize: 'var(--fs-xs)' }}>
              {COPY.SETTINGS_SECURITY_BIOMETRIC}
            </span>
            {biometricOn ? (
              <button className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }} onClick={handleTurnOffBiometric}>
                {COPY.SETTINGS_SECURITY_TURN_OFF}
              </button>
            ) : (
              <Link href="/pin/setup" className="btn-ghost" style={{ fontSize: 'var(--fs-xs)' }}>
                {COPY.SETTINGS_SECURITY_SET_PIN}
              </Link>
            )}
          </div>
        )}
      </div>

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