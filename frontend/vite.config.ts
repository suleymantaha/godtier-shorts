/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolveManualChunk } from './build/manualChunks'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  build: {
    // Three.js publishes its core as a single ESM entry; after splitting the surrounding
    // react-three ecosystem, the remaining lazy-loaded core chunk still lands above 500 kB.
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks: resolveManualChunk,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    testTimeout: 10000,
  },
})
