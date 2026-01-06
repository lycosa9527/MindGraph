import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { readFileSync } from 'fs'

// Read version from VERSION file (single source of truth)
const version = readFileSync(resolve(__dirname, '../VERSION'), 'utf-8').trim()

export default defineConfig({
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(version),
    __BUILD_TIME__: JSON.stringify(Date.now()),
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:9527',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:9527',
        ws: true,
      },
      '/static': {
        target: 'http://localhost:9527',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:9527',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    // Element Plus is ~1MB (expected for a full UI framework)
    // Suppress warning since we've already split vendors optimally
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        // Split vendor libraries into separate chunks for better caching
        manualChunks: {
          // Vue core libraries
          'vendor-vue': ['vue', 'vue-router', 'pinia'],
          // UI framework (largest dependency)
          'vendor-element-plus': ['element-plus', '@element-plus/icons-vue'],
          // VueFlow (diagram visualization)
          'vendor-vueflow': [
            '@vue-flow/core',
            '@vue-flow/background',
            '@vue-flow/controls',
            '@vue-flow/minimap',
          ],
          // Utilities
          'vendor-utils': ['axios', '@vueuse/core', 'mitt', 'dompurify', 'markdown-it'],
        },
      },
    },
  },
})
