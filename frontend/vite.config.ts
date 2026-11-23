import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Keep localhost defaults for normal Windows development.
// Docker Compose overrides these with service names.
const backendTarget = process.env.BACKEND_PROXY_TARGET ?? 'http://localhost:5049'
const pythonTarget = process.env.PYTHON_PROXY_TARGET ?? 'http://127.0.0.1:5000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    proxy: {
      '/backend-api': {
        target: backendTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/backend-api/, '/api'),
      },
      '/python-api': {
        target: pythonTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/python-api/, '/api'),
      },
      '/ticket-image': {
        target: pythonTarget,
        changeOrigin: true,
      },
    },
  },
})
