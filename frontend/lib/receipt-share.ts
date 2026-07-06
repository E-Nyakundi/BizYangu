/**
 * BizYangu — receipt image capture + share.
 *
 * "Send it as-is via WhatsApp" means an image of the actual designed
 * receipt — whatever theme is currently active (dark or light) — not
 * a reformatted text message. This renders the on-screen ReceiptCard
 * DOM node to a PNG and hands it to whatever share mechanism is
 * available for the current platform:
 *
 *   1. Installed APK (Capacitor.isNativePlatform() === true) — real
 *      native Android share sheet with the image attached; user picks
 *      WhatsApp. Requires the FileProvider setup in AndroidManifest.xml
 *      / file_paths.xml, which is already in place.
 *   2. Browser (mobile web preview via ngrok, desktop, or native
 *      fallback) — Web Share API with files, e.g. Chrome on Android and
 *      Safari on iOS both support sharing an image directly to
 *      WhatsApp this way.
 *   3. Last resort: download the PNG so it can be attached by hand —
 *      only hit when neither share mechanism above is available.
 *
 * The platform check happens BEFORE any of the share calls: most
 * browsers only honor navigator.share() for a short window after the
 * click (transient user activation). Previously this always attempted
 * the native path first regardless of platform, which could only ever
 * fail in a browser — but the dynamic plugin imports + failed
 * filesystem write still burned real time, so by the time it fell back
 * to Web Share the click's activation window was often already gone,
 * and it silently dropped all the way to auto-downloading the file.
 * Deciding up front means each environment goes straight to the one
 * path that can actually work for it.
 *
 * Dynamic imports for the native-only plugins, same pattern as
 * lib/offline-queue.ts and lib/push.ts, so `next dev` / desktop web
 * never chokes on native-only Capacitor plugins.
 *
 * Theme fidelity: the background color is read from the live
 * `--surface-0` CSS custom property at capture time, not hardcoded —
 * so a receipt captured while the app is in light mode renders light,
 * and one captured in dark mode renders dark. Nothing here needs to
 * "know" which theme is active; it just reflects whatever is on
 * screen at the moment of the tap.
 *
 * Note: the receipt's perforated top/bottom edge is drawn via CSS
 * ::before/::after (see ReceiptCard.tsx). html2canvas has patchy
 * support for generated pseudo-element content — the shared image may
 * render with square edges even though the on-screen card shows the
 * scalloped cut. Everything else (business info, items, total,
 * badges, barcode) captures faithfully.
 */

import type { Transaction } from './types'
import { Capacitor } from '@capacitor/core'

async function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => {
      const result = reader.result as string
      resolve(result.split(',')[1] ?? '')
    }
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}

async function renderToPngBlob(node: HTMLElement): Promise<Blob> {
  const { default: html2canvas } = await import('html2canvas')

  // Read the *currently active* theme's background — this is what
  // makes the capture "as-is, dark or light" rather than baked to
  // one theme.
  const bg =
    getComputedStyle(document.documentElement).getPropertyValue('--surface-0').trim() || '#0A0A0A'

  const canvas = await html2canvas(node, {
    backgroundColor: bg,
    scale: 2, // crisp on high-DPI phone screens
    useCORS: true,
  })

  return new Promise((resolve, reject) => {
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Could not render receipt image'))), 'image/png')
  })
}

export type ShareReceiptResult = { method: 'native' | 'web-share' | 'download' }

// Web Share with files needs to fire as close to the original click as
// possible — most browsers only honor navigator.share() for a few seconds
// after a user gesture ("transient activation"). Every extra await before
// the call eats into that window. The previous version always attempted
// the native Capacitor path first (dynamic plugin imports + a filesystem
// write) even when running in a plain mobile browser — where those calls
// can only ever fail — before falling back to Web Share. By the time it
// got there the gesture window was often already gone, so it silently
// fell all the way through to auto-downloading the PNG instead of
// actually opening a share sheet. Checking the platform up front means
// each environment goes straight to the one path that can work for it.
async function shareViaWebShare(blob: Blob, filename: string, caption: string): Promise<boolean> {
  try {
    const file = new File([blob], filename, { type: 'image/png' })
    if (
      typeof navigator !== 'undefined' &&
      typeof navigator.canShare === 'function' &&
      navigator.canShare({ files: [file] })
    ) {
      await navigator.share({ files: [file], title: 'Risiti', text: caption })
      return true
    }
  } catch (err) {
    // AbortError = user cancelled the native share sheet — treat as done,
    // not a failure that should fall through to auto-downloading a file
    // they didn't ask for.
    if (err instanceof Error && err.name === 'AbortError') return true
  }
  return false
}

export async function shareReceiptImage(
  node: HTMLElement,
  transaction: Transaction,
  businessName: string
): Promise<ShareReceiptResult> {
  const blob = await renderToPngBlob(node)
  const filename = `risiti-${transaction.reference_number}.png`
  const caption = `Risiti — ${businessName} · ${transaction.reference_number}`

  if (Capacitor.isNativePlatform()) {
    // Real installed APK — use the native Android share sheet so the
    // image attaches directly (FileProvider is configured for this in
    // AndroidManifest.xml / file_paths.xml).
    try {
      const base64 = await blobToBase64(blob)
      const { Filesystem, Directory } = await import('@capacitor/filesystem')
      const { Share } = await import('@capacitor/share')

      const written = await Filesystem.writeFile({
        path: filename,
        data: base64,
        directory: Directory.Cache,
      })

      await Share.share({
        title: 'Risiti',
        text: caption,
        files: [written.uri],
        dialogTitle: 'Tuma Risiti',
      })

      return { method: 'native' }
    } catch {
      // Fall through to Web Share / download below — some native
      // webviews still expose navigator.share.
    }
  }

  // Browser (ngrok field-testing, desktop preview, or native fallback) —
  // Web Share API with files, called with nothing awaited beforehand.
  if (await shareViaWebShare(blob, filename, caption)) {
    return { method: 'web-share' }
  }

  // Last resort — neither share path is available on this device/browser,
  // so download the PNG so it can be attached by hand.
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
  return { method: 'download' }
}
