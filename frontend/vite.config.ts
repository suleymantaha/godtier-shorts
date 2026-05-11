/// <reference types="vitest/config" />
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolveManualChunk } from './build/manualChunks'
import { resolveWatchConfig } from './build/watchConfig'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

export default defineConfig({
  // Repo kökündeki .env içinden VITE_* değişkenlerini oku (backend ile aynı dosya).
  envDir: repoRoot,
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    watch: resolveWatchConfig(),
  },
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
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'html'],
      reportsDirectory: './coverage',
      thresholds: {
        statements: 75,
        branches: 65,
        functions: 75,
        lines: 75,
      },
    },
  },
})
