import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // LN Design System palette
        'teal':       '#00E5C4',
        'teal-dim':   '#00A890',
        'off-white':  '#F2F0EB',
        'error':      '#FF4D6D',
        'violet':     '#A78BFA',
        'muted':      '#6B7280',
        // Surfaces
        'surface-0':  '#0A0A0A',
        'surface-1':  '#111318',
        'surface-2':  '#1C1F26',
        'surface-3':  '#252830',
        'surface-4':  '#2F3239',
      },
      fontFamily: {
        sans: ['var(--font-space-grotesk)', 'Space Grotesk', 'sans-serif'],
        mono: ['var(--font-jetbrains-mono)', 'JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}

export default config
