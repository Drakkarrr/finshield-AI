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
        ink:        { DEFAULT: '#1A1A2E', secondary: '#4A5568', muted: '#6B7280', light: '#9CA3AF' },
        // Brand accents — matching website
        accent:     { DEFAULT: '#C8870E', light: '#E5A628', dark: '#A06E0A', muted: '#D4930D' },
        teal:       { DEFAULT: '#1A9E8F', light: '#22B8A6', dark: '#147A6E' },
        navy:       { DEFAULT: '#0A1628', light: '#132038', mid: '#1B2D4A' },
        // Semantic
        success:    { DEFAULT: '#16A34A', light: '#DCFCE7', bg: '#F0FDF4' },
        warning:    { DEFAULT: '#E5A628', light: '#FEF3C7', bg: '#FFFBEB' },
        danger:     { DEFAULT: '#DC2626', light: '#FEE2E2', bg: '#FEF2F2' },
        info:       { DEFAULT: '#1A9E8F', light: '#D1FAE5', bg: '#F0FDFA' },
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
