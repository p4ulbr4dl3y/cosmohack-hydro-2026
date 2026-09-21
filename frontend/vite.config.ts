/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  // Build straight into the FastAPI static directory; every runtime asset
  // (assets/, data/, icons/, vendor/) is emitted from frontend/public + bundle.
  build: {
    outDir: '../src/service/static',
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    globals: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Vendored offline assets (Leaflet, fonts) are served by the FastAPI static mount
      '/vendor': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
