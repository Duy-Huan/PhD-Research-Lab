/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

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
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    testTimeout: 15000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      exclude: ['node_modules/', 'dist/', 'src/test/'],
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/vendor': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/img': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/assets': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
    },
  },
});
