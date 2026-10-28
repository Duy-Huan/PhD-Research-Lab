/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

// Allow an isolated real backend during development and browser regression runs.
const backendUrl = process.env.PHDLAB_BACKEND_URL || 'http://127.0.0.1:8765';

export default defineConfig({
  plugins: [react()],
  base: '/dist/',
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: resolve(__dirname, 'react.html'),
    },
    chunkSizeWarningLimit: 1500,
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    testTimeout: 15000,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      reporter: ['text', 'json', 'json-summary', 'html', 'lcov'],
      exclude: ['node_modules/', 'dist/', 'src/test/', 'src/**/*.test.{ts,tsx}'],
      // v6.6.2 owner policy: a hard ratchet toward 100% (raise as coverage grows, never lower).
      thresholds: { lines: 66, branches: 65, functions: 53, statements: 65 },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/vendor': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/img': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/assets': {
        target: backendUrl,
        changeOrigin: true,
      },
    },
  },
});
