/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Be Vietnam Pro"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Emerald is the shared Local Explorer accent across the public and portal apps.
        brand: {
          50: '#ecfdf5',
          100: '#d1fae5',
          200: '#a7f3d0',
          300: '#6ee7b7',
          400: '#34d399',
          500: '#10b981',
          600: '#047857',
          700: '#065f46',
          800: '#064e3b',
          900: '#022c22',
        },
        ink: '#0f2747',
      },
      boxShadow: {
        card: '0 1px 2px rgba(15, 39, 71, 0.04), 0 1px 3px rgba(15, 39, 71, 0.06)',
        pop: '0 18px 40px -24px rgba(15, 39, 71, 0.32)',
      },
    },
  },
  plugins: [],
}
