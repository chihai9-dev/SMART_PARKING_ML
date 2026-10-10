import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/backend-api': {
        target: 'http://localhost:5049',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/backend-api/, '/api'),
      },
      '/python-api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/python-api/, '/api'),
      },
      '/ticket-image': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
})
