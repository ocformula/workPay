import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/static/frontend/',
  server: {
    proxy: {
      '^/api': {
        target: 'http://localhost:8888',
      },
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
})
