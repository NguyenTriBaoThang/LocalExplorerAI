/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Be Vietnam Pro"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Ocean blue of the Local Explorer logo; teal is its secondary accent.
        brand: {
          50: '#eff8ff',
          100: '#dbeefe',
          200: '#bfe2fe',
          300: '#93cffd',
          400: '#60b3fa',
          500: '#3b93f5',
          600: '#1f74e0',
          700: '#1a5dc0',
          800: '#1b4d9b',
          900: '#1c427b',
        },
        ink: '#0f2747',
      },
      boxShadow: {
        card: '0 1px 2px rgba(15, 39, 71, 0.04), 0 1px 3px rgba(15, 39, 71, 0.06)',
        pop: '0 16px 40px -12px rgba(15, 39, 71, 0.22)',
      },
    },
  },
  plugins: [],
}
