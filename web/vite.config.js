import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// GitHub Pages serves the site at https://david-zaev.github.io/niva/
const base = process.env.NIVA_BASE ?? '/niva/'
const apiOrigin = 'https://niva-api.92-5-133-111.sslip.io'

export default defineConfig({
  base,
  // the theme lives in ../brand so there is one copy of it
  server: { fs: { allow: ['..'] } },
  plugins: [
    react(),
    VitePWA({
      // autoUpdate while we deploy many times a day; the "Update ready" button comes in M6
      registerType: 'autoUpdate',
      includeAssets: ['icons/*.png', 'icons/*.svg', 'icons/favicon.ico'],
      manifest: {
        name: 'Niva',
        short_name: 'Niva',
        description: 'Crop rotation advice from NASA data and your own soil sensor',
        lang: 'en',
        theme_color: '#0b0b0b',
        background_color: '#0b0b0b',
        display: 'standalone',
        start_url: base,
        scope: base,
        icons: [
          { src: 'icons/pwa-64x64.png', sizes: '64x64', type: 'image/png' },
          { src: 'icons/pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icons/maskable-icon-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,json,woff2}'],
        navigateFallback: `${base}index.html`,
        runtimeCaching: [
          {
            // API answers: network first, fall back to the last saved answer
            urlPattern: ({ url }) => url.origin === apiOrigin,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'niva-api',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
        ],
      },
    }),
  ],
})
