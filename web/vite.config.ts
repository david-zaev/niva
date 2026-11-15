import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// In development the browser talks to /api and Vite forwards it to the Niva server,
// so no CORS setup is needed. Point NIVA_API at http://127.0.0.1:8000 to use a local backend.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const api = env.NIVA_API || 'https://niva-api.92-5-133-111.sslip.io'
  return {
    plugins: [
      react(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['icon.svg', 'apple-touch-icon.png'],
        manifest: {
          name: 'Niva: field advice from space and soil',
          short_name: 'Niva',
          description: 'Field advice for farms in North Macedonia from Sentinel-2, NASA data and an ESP32 field system.',
          theme_color: '#141414',
          background_color: '#F2F2F0',
          display: 'standalone',
          orientation: 'any',
          start_url: '/',
          icons: [
            { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
            { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          ],
        },
        workbox: {
          globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
          navigateFallbackDenylist: [/^\/api\//],
          runtimeCaching: [
            {
              // Map tiles: keep what the farmer has already looked at, for the field with no signal.
              urlPattern: ({ url }) => /basemaps\.cartocdn\.com|tiles\.maps\.eox\.at/.test(url.hostname),
              handler: 'CacheFirst',
              options: { cacheName: 'map-tiles', expiration: { maxEntries: 600, maxAgeSeconds: 60 * 60 * 24 * 30 } },
            },
            {
              urlPattern: ({ url }) => /open-meteo\.com|power\.larc\.nasa\.gov|rest\.isric\.org|earth-search/.test(url.hostname),
              handler: 'NetworkFirst',
              options: { cacheName: 'earth-data', networkTimeoutSeconds: 12, expiration: { maxEntries: 60, maxAgeSeconds: 60 * 60 * 24 * 7 } },
            },
          ],
        },
      }),
    ],
    server: {
      port: 5173,
      proxy: { '/api': { target: api, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') } },
    },
    test: { environment: 'node' },
  }
})
