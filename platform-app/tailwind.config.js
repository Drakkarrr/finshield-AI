/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Warm neutrals — matching website palette
        bg:         { DEFAULT: '#F8F7F4', alt: '#F0EDE8', dark: '#0A1628' },
        surface:    { DEFAULT: '#FFFFFF', hover: '#F5F4F0', raised: '#FAFAF8' },
        border:     { DEFAULT: '#E2DFD8', light: '#EDEBE6', dark: '#D4D0C8' },
        // Text
        ink:        { DEFAULT: '#1A1A2E', secondary: '#4A5568', muted: '#5F6573', light: '#9CA3AF' },
        // Brand accents — matching website. `fg` is the accent as text on light surfaces (WCAG AA).
        accent:     { DEFAULT: '#C8870E', light: '#E5A628', dark: '#A06E0A', muted: '#D4930D', fg: '#875C08' },
        teal:       { DEFAULT: '#1A9E8F', light: '#22B8A6', dark: '#147A6E' },
        navy:       { DEFAULT: '#0A1628', light: '#132038', mid: '#1B2D4A' },
        // Semantic. DEFAULT is for fills/dots/bars; `fg` is the text colour on `bg`/`light` (WCAG AA).
        success:    { DEFAULT: '#16A34A', light: '#DCFCE7', bg: '#F0FDF4', fg: '#15803D' },
        warning:    { DEFAULT: '#E5A628', light: '#FEF3C7', bg: '#FFFBEB', fg: '#92400E' },
        danger:     { DEFAULT: '#DC2626', light: '#FEE2E2', bg: '#FEF2F2', fg: '#B91C1C' },
        info:       { DEFAULT: '#1A9E8F', light: '#D1FAE5', bg: '#F0FDFA', fg: '#0F766E' },
      },
      fontFamily: {
        // Loaded by next/font in src/app/layout.tsx (self-hosted, so the CSP needs no font origins)
        sans: ['var(--font-inter)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      fontSize: {
        // Below text-xs: dense meta text (table sub-lines, timestamps). Never for body copy.
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      spacing: {
        sidebar: '16rem',
      },
      maxHeight: {
        modal: '85vh',
      },
      zIndex: {
        topbar: '40',
        sidebar: '50',
        dropdown: '60',
        modal: '70',
      },
      boxShadow: {
        'card':     '0 1px 3px rgba(10, 22, 40, 0.04), 0 1px 2px rgba(10, 22, 40, 0.06)',
        'card-lg':  '0 4px 12px rgba(10, 22, 40, 0.08)',
        'card-xl':  '0 8px 24px rgba(10, 22, 40, 0.12)',
        'dropdown': '0 12px 40px rgba(10, 22, 40, 0.15)',
      },
      animation: {
        'fade-in-up': 'fadeInUp 0.4s ease both',
        'slide-in': 'slideIn 0.3s ease both',
      },
      keyframes: {
        fadeInUp: {
          '0%':   { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideIn: {
          '0%':   { transform: 'translateX(-100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
