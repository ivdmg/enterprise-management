import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), mode === 'showcase' && {
    name: 'showcase-title',
    transformIndexHtml: html => html.replace('<title>Enterprise Hub</title>', '<title>Система мониторинга предприятия</title>'),
  }],
  define: mode === 'showcase' ? {
    'import.meta.env.VITE_API_ORIGIN': JSON.stringify(''),
    'import.meta.env.VITE_PLATFORM_API_ORIGIN': JSON.stringify(''),
    'import.meta.env.VITE_PLATFORM_CLIENT': JSON.stringify('false'),
    'import.meta.env.VITE_ALLOW_REGISTRATION': JSON.stringify('false'),
  } : undefined,
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: mode === 'demo' ? undefined : {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
}))
