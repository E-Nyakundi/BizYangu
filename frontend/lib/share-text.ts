/**
 * BizYangu — plain text sharing (EOD summary → WhatsApp).
 * Same platform-detection pattern as receipt-share.ts, simplified for
 * text-only content — no image capture needed here.
 */

import { Capacitor } from '@capacitor/core'

export async function shareText(text: string): Promise<void> {
  if (Capacitor.isNativePlatform()) {
    try {
      const { Share } = await import('@capacitor/share')
      await Share.share({ text })
      return
    } catch {
      // fall through to clipboard below
    }
  } else if (typeof navigator !== 'undefined' && navigator.share) {
    try {
      await navigator.share({ text })
      return
    } catch {
      // user cancelled or unsupported — fall through to clipboard
    }
  }

  // Last resort: copy to clipboard so it can be pasted into WhatsApp by hand.
  if (typeof navigator !== 'undefined' && navigator.clipboard) {
    await navigator.clipboard.writeText(text)
  }
}