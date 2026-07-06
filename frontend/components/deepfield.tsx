'use client'

import { useEffect, useRef } from 'react'

interface DeepfieldProps {
  position?: 'fixed' | 'absolute' | 'relative'
  zIndex?: number
  enableAnimation?: boolean
  opacity?: number
  className?: string
}

export default function Deepfield({
  position = 'fixed',
  zIndex = -1,
  enableAnimation = true,
  opacity = 1,
  className = '',
}: DeepfieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!enableAnimation || !canvasRef.current) return

    const canvas = canvasRef.current
    const rawCtx = canvas.getContext('2d', { alpha: false })
    if (!rawCtx) return
    // Re-bind to an explicitly non-null const — TS's control-flow
    // narrowing from the guard above doesn't carry into `render()`
    // below, since it's a function declaration invoked later via
    // requestAnimationFrame rather than inline.
    const ctx: CanvasRenderingContext2D = rawCtx

    // Sizing
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let w = window.innerWidth
    let h = window.innerHeight

    canvas.width = Math.floor(w * dpr)
    canvas.height = Math.floor(h * dpr)
    canvas.style.width = w + 'px'
    canvas.style.height = h + 'px'
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    // Helpers
    const lerp = (a: number, b: number, t: number) => a + (b - a) * t
    const lerpC = (
      c1: [number, number, number],
      c2: [number, number, number],
      t: number
    ): [number, number, number] => [lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t)]

    // Colors
    const darkVoid: [number, number, number] = [10, 10, 10]
    const lightVoid: [number, number, number] = [244, 242, 237]

    let animId: number | null = null
    let lastTime = performance.now()
    let simTime = 0
    let paused = false

    const handleVis = () => {
      paused = document.hidden
    }
    document.addEventListener('visibilitychange', handleVis)

    // Respect prefers-reduced-motion — per the migration plan's own
    // guidance, this ambient loop should never keep running for someone
    // who's asked their OS to minimize motion. We still draw one frame
    // (so the background isn't blank) but never schedule another.
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const handleResize = () => {
      w = window.innerWidth
      h = window.innerHeight
      canvas.width = Math.floor(w * dpr)
      canvas.height = Math.floor(h * dpr)
      canvas.style.width = w + 'px'
      canvas.style.height = h + 'px'
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    window.addEventListener('resize', handleResize)

    function render(now: number) {
      if (paused) {
        animId = requestAnimationFrame(render)
        return
      }

      const dt = Math.min((now - lastTime) / 1000, 0.05)
      lastTime = now
      simTime += dt

      // Get theme
      const isDark = document.documentElement.getAttribute('data-theme') !== 'light'
      const themeMix = isDark ? 0 : 1

      // Background
      const bgCol = lerpC(darkVoid, lightVoid, themeMix)
      ctx.fillStyle = `rgb(${bgCol[0] | 0},${bgCol[1] | 0},${bgCol[2] | 0})`
      ctx.fillRect(0, 0, w, h)

      // Nebula orbs
      if (isDark) {
        for (let i = 0; i < 6; i++) {
          const angle = ((i + 0.5) / 6) * Math.PI * 2 - Math.PI
          const dist = Math.max(w, h) * 0.3
          const cx = w / 2 + Math.cos(angle) * dist
          const cy = h / 2 + Math.sin(angle) * dist

          const pulse = 0.85 + 0.15 * Math.sin(simTime * 0.5 + i)
          const alpha = 0.025 * pulse

          const r = Math.max(w, h) * 0.35
          const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r)
          grad.addColorStop(0, `rgba(0,229,196,${alpha.toFixed(4)})`)
          grad.addColorStop(0.5, `rgba(0,229,196,${(alpha * 0.3).toFixed(4)})`)
          grad.addColorStop(1, 'rgba(0,229,196,0)')
          ctx.fillStyle = grad
          ctx.fillRect(0, 0, w, h)
        }
      }

      // Sweep gradient
      const sweepX = (0.5 + 0.3 * Math.sin(simTime * 0.15)) * w
      const sweepY = (0.5 + 0.3 * Math.cos(simTime * 0.12)) * h
      const sweepAlpha = isDark ? 0.045 : 0.022
      const sweepGrad = ctx.createRadialGradient(sweepX, sweepY, 0, sweepX, sweepY, Math.max(w, h) * 0.55)
      sweepGrad.addColorStop(0, `rgba(0,229,196,${sweepAlpha})`)
      sweepGrad.addColorStop(1, 'rgba(0,229,196,0)')
      ctx.fillStyle = sweepGrad
      ctx.fillRect(0, 0, w, h)

      // Light shafts
      if (isDark) {
        for (let i = 0; i < 2; i++) {
          const sy = (0.3 + Math.sin(simTime * 0.3 + i) * 0.2) * h
          const sx = (0.2 + i * 0.6) * w + Math.sin(simTime * 0.2 + i) * w * 0.1
          const shaftGrad = ctx.createLinearGradient(sx, sy, sx, sy + h)
          const shaftAlpha = 0.03 * (1 - Math.abs(Math.sin(simTime * 0.1 + i)) * 0.3)
          shaftGrad.addColorStop(0, `rgba(0,229,196,${shaftAlpha.toFixed(4)})`)
          shaftGrad.addColorStop(1, 'rgba(0,229,196,0)')
          ctx.fillStyle = shaftGrad
          ctx.fillRect(0, 0, w, h)
        }
      }

      if (!reducedMotion) {
        animId = requestAnimationFrame(render)
      }
    }

    animId = requestAnimationFrame(render)

    return () => {
      if (animId !== null) cancelAnimationFrame(animId)
      document.removeEventListener('visibilitychange', handleVis)
      window.removeEventListener('resize', handleResize)
    }
  }, [enableAnimation])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position,
        inset: 0,
        width: '100%',
        height: '100%',
        zIndex,
        opacity,
        display: 'block',
      }}
      className={className}
    />
  )
}
