/**
 * BizYangu — Biashara Systems wordmark.
 *
 * Theme-aware: renders both mark variants and lets CSS pick which one is
 * visible via the [data-theme] attribute set on <html> by lib/theme.ts.
 * This avoids a flash-of-wrong-logo on load (no JS theme check needed —
 * the DOM attribute is set synchronously before paint).
 *
 * - dark theme  -> biashara-mark-light.png (light mark, for dark backgrounds)
 * - light theme -> biashara-mark-dark.png  (dark mark, for light backgrounds)
 */

type LogoProps = {
  height?: number
  className?: string
}

export default function Logo({ height = 32, className }: LogoProps) {
  return (
    <span
      className={className}
      style={{ display: 'inline-flex', alignItems: 'center', height }}
    >
      <img
        src="/logos/biashara-mark-light.png"
        alt="Biashara Systems"
        height={height}
        className="logo-mark logo-mark--dark-theme"
        style={{ height, width: 'auto' }}
      />
      <img
        src="/logos/biashara-mark-dark.png"
        alt="Biashara Systems"
        height={height}
        className="logo-mark logo-mark--light-theme"
        style={{ height, width: 'auto' }}
      />
    </span>
  )
}
