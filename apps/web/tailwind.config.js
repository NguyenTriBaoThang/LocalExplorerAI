/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Be Vietnam Pro"', 'system-ui', 'sans-serif'],
        display: ['"Be Vietnam Pro"', 'system-ui', 'sans-serif'],
      },
      colors: { ink: '#18231f', moss: '#3d6555', paper: '#f7f7f3', citrus: '#e5ef9f' }
    }
  },
  plugins: [],
}
