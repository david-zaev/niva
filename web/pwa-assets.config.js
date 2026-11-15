import { defineConfig, minimal2023Preset } from '@vite-pwa/assets-generator/config'

// Builds the app icons (64/192/512, maskable 512, apple-touch 180, favicon) from the brand logo.
// Run: npm run icons
const deepGreen = { background: '#145C38', fit: 'contain' }

export default defineConfig({
  headLinkOptions: { preset: '2023' },
  preset: {
    ...minimal2023Preset,
    maskable: { ...minimal2023Preset.maskable, resizeOptions: deepGreen },
    apple: { ...minimal2023Preset.apple, resizeOptions: deepGreen },
  },
  images: ['public/icons/logo.svg'],
})
