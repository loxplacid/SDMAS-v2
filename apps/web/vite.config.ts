import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'
import fs from 'fs'

/**
 * Universal search: the official sqlite3 WASM worker resolves
 * `sqlite3.wasm` and the OPFS async proxy relative to its own URL, so
 * those assets (plus the worker script) must be served as static files.
 * Copy them from the npm package into `public/` at build/dev start.
 */
const SQLITE_WASM_PKG = path.resolve(
  __dirname,
  'node_modules/@sqlite.org/sqlite-wasm/dist',
)

function sqliteWasmAssets(): Plugin {
  const copy = () => {
    const files: [string, string][] = [
      ['sqlite3-worker1.mjs', 'sqlite3-worker1.mjs'],
      ['sqlite3.wasm', 'sqlite3.wasm'],
      ['sqlite3-opfs-async-proxy.js', 'sqlite3-opfs-async-proxy.js'],
    ]
    const outDir = path.resolve(__dirname, 'public')
    fs.mkdirSync(outDir, { recursive: true })
    for (const [src, dest] of files) {
      const from = path.join(SQLITE_WASM_PKG, src)
      if (!fs.existsSync(from)) continue
      fs.copyFileSync(from, path.join(outDir, dest))
    }
  }
  return {
    name: 'sqlite-wasm-assets',
    buildStart: copy,
  }
}

export default defineConfig({
  plugins: [
    sqliteWasmAssets(),
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icons/*.svg'],
      manifest: {
        name: 'SDMAS - School Data Management & Analytics System',
        short_name: 'SDMAS',
        description: 'Manage students, academics, attendance, fees, and analytics — a unified platform for modern educational institutions.',
        theme_color: '#f8fafc',
        background_color: '#f8fafc',
        display: 'standalone',
        orientation: 'any',
        start_url: '/',
        scope: '/',
        categories: ['education', 'productivity'],
        icons: [
          { src: '/icons/icon-192.svg', sizes: '192x192', type: 'image/svg+xml', purpose: 'any maskable' },
          { src: '/icons/icon-512.svg', sizes: '512x512', type: 'image/svg+xml', purpose: 'any maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2,wasm,mjs}'],
        runtimeCaching: [
          {
            urlPattern: /^https?:\/\/.*\/api\//i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 },
              networkTimeoutSeconds: 5,
            },
          },
          {
            urlPattern: /^https?:\/\/.*\/auth\//i,
            handler: 'NetworkOnly',
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Core React framework
          'vendor-react': ['react', 'react-dom'],
          // Routing
          'vendor-router': ['react-router-dom'],
          // Chart library
          'vendor-charts': ['recharts'],
        },
      },
    },
    // Increase chunk size warning limit — code-split pages will be naturally smaller
    chunkSizeWarningLimit: 400,
  },
  server: {
    port: 5173,
    // Cross-origin isolation enables SharedArrayBuffer, which the sqlite3
    // OPFS VFS requires for persistent local indexes (see search-db.ts).
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/students': 'http://localhost:8000',
      '/attendance': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/ready': 'http://localhost:8000',
    },
  },
})