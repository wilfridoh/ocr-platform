/** @type {import('tailwindcss').Config} */
// Tokens de docs/09-guia-visual-frontend.md (fuente: diseno/maqueta.html).
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#F5F6FA',
        surface: '#FFFFFF',
        ink: { DEFAULT: '#0F172A', 2: '#475569', 3: '#64748B' },
        line: { DEFAULT: '#E2E8F0', 2: '#F1F5F9' },
        brand: { DEFAULT: '#4338CA', h: '#3730A3', soft: '#EEF0FF', line: '#C7CCF8' },
        ok: { DEFAULT: '#047857', soft: '#E6F6EF' },
        warn: { DEFAULT: '#B45309', soft: '#FEF3C7' },
        err: { DEFAULT: '#B91C1C', soft: '#FEE2E2' },
        side: { DEFAULT: '#0F172A', ink: '#94A3B8', on: '#312E81' },
        // La app existente usa indigo-*: se alinea con la marca de la maqueta (indigo-600 pasa a ser #4338CA).
        indigo: {
          50: '#EEF0FF',
          100: '#E0E4FD',
          200: '#C7CCF8',
          300: '#A5ACF2',
          400: '#818CF8',
          500: '#5B57D6',
          600: '#4338CA',
          700: '#3730A3',
          800: '#312E81',
          900: '#272565',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      borderRadius: { card: '10px' },
      boxShadow: { card: '0 1px 2px rgba(15,23,42,.06), 0 1px 3px rgba(15,23,42,.05)' },
    },
  },
  plugins: [],
}
