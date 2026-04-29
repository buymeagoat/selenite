import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0D0E11',
        panel: '#13161C',
        border: '#1E2128',
        accent: '#F5A623',
        text: '#E8E9EC',
        muted: '#6B7280',
      },
      fontFamily: {
        serif: ['"DM Serif Display"', 'serif'],
        mono: ['"Geist Mono"', 'monospace'],
        sans: ['Geist', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config
