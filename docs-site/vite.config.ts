import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Relative base + hash routing => works under https://<user>.github.io/<repo>/ without hardcoding either.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: { chunkSizeWarningLimit: 300 },
})
