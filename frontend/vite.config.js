import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // strictPort: fail fast instead of moving to 5174, which the backend CORS_ORIGINS would reject.
  server: { port: 5173, strictPort: true },
  test: { environment: 'jsdom' },
})
