/**
 * BizYangu — offline sale queue.
 *
 * When a sale POST fails because the device is offline, we store it here and
 * sync it on the next successful network request.
 *
 * Storage: tries @capacitor/preferences (native), falls back to localStorage
 * (web/dev). Both are key-value; we store a JSON array under QUEUE_KEY.
 */

import type { SaleCreatePayload } from './transactions'

const QUEUE_KEY = 'bizyango:offline_queue'

// ── Storage adapter ──────────────────────────────────────────────────────────

async function storageGet(key: string): Promise<string | null> {
  try {
    // Dynamic import so Next.js SSR doesn't choke on Capacitor
    const { Preferences } = await import('@capacitor/preferences')
    const { value } = await Preferences.get({ key })
    return value
  } catch {
    // Capacitor not available (web browser dev mode)
    return localStorage.getItem(key)
  }
}

async function storageSet(key: string, value: string): Promise<void> {
  try {
    const { Preferences } = await import('@capacitor/preferences')
    await Preferences.set({ key, value })
  } catch {
    localStorage.setItem(key, value)
  }
}

// ── Queue types ──────────────────────────────────────────────────────────────

export interface QueuedSale {
  id: string           // local UUID so we can deduplicate on sync
  payload: SaleCreatePayload
  queuedAt: string    // ISO timestamp
  attempts: number
}

// ── Public API ───────────────────────────────────────────────────────────────

export async function enqueue(payload: SaleCreatePayload): Promise<QueuedSale> {
  const queue = await getQueue()
  const entry: QueuedSale = {
    id: crypto.randomUUID(),
    payload,
    queuedAt: new Date().toISOString(),
    attempts: 0,
  }
  queue.push(entry)
  await saveQueue(queue)
  return entry
}

export async function getQueue(): Promise<QueuedSale[]> {
  const raw = await storageGet(QUEUE_KEY)
  if (!raw) return []
  try {
    return JSON.parse(raw) as QueuedSale[]
  } catch {
    return []
  }
}

export async function removeFromQueue(id: string): Promise<void> {
  const queue = await getQueue()
  await saveQueue(queue.filter((item) => item.id !== id))
}

export async function clearQueue(): Promise<void> {
  await saveQueue([])
}

export async function queueLength(): Promise<number> {
  const queue = await getQueue()
  return queue.length
}

/**
 * Attempt to sync all queued sales.
 * Returns { synced, failed } counts.
 */
export async function syncQueue(
  createSaleFn: (payload: SaleCreatePayload) => Promise<unknown>
): Promise<{ synced: number; failed: number }> {
  const queue = await getQueue()
  let synced = 0
  let failed = 0

  for (const item of queue) {
    try {
      await createSaleFn(item.payload)
      await removeFromQueue(item.id)
      synced++
    } catch {
      // Increment attempt counter but keep in queue
      item.attempts++
      failed++
    }
  }

  // Persist updated attempt counts for items that failed
  if (failed > 0) {
    const remaining = await getQueue()
    const updatedRemaining = remaining.map((r) => {
      const found = queue.find((q) => q.id === r.id)
      return found ? { ...r, attempts: found.attempts } : r
    })
    await saveQueue(updatedRemaining)
  }

  return { synced, failed }
}

// ── Internal ─────────────────────────────────────────────────────────────────

async function saveQueue(queue: QueuedSale[]): Promise<void> {
  await storageSet(QUEUE_KEY, JSON.stringify(queue))
}
