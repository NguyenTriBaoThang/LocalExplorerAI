import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 8081,
    allowedHosts: true,
    proxy: {
      '/api': process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
      // Imported catalog photos are shared with the web app.
      '/images/places/': process.env.WEB_PROXY_TARGET ?? 'http://127.0.0.1:8080',
    },
  },
})
