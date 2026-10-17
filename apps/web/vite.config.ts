import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 8080,
    allowedHosts: true,
    hmr: {
      clientPort: 8080,
    },
    proxy: {
      '/api': {
        target: process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        ws: true,
      },
      '/health': process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
    },
  },
})
