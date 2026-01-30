import { defineConfig, Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve, dirname } from 'path'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))


// Read version from VERSION file (single source of truth)
const version = readFileSync(resolve(__dirname, '../VERSION'), 'utf-8').trim()

// Get backend host from environment variable (for WSL/remote scenarios)
// Default to localhost for normal development
// For WSL: Use Windows host IP (e.g., VITE_BACKEND_HOST=http://172.x.x.x:9527)
const backendHost = process.env.VITE_BACKEND_HOST || 'http://localhost:9527'
const backendHostWs = backendHost.replace('http://', 'ws://').replace('https://', 'wss://')

export default defineConfig({
  plugins: [vue(), tailwindcss()],
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
    port: 5173, // Use Vite's default port 5173 to avoid conflicts
    host: process.env.VITE_HOST || '127.0.0.1', // Default to 127.0.0.1 (IPv4) to avoid IPv6 permission issues in WSL; set VITE_HOST=0.0.0.0 for WSL/remote access
    strictPort: false, // Allow Vite to use another port if 5173 is taken
    proxy: {
      '/api': {
        target: backendHost,
        changeOrigin: true,
      },
      '/ws': {
        target: backendHostWs,
        ws: true,
      },
      '/static': {
        target: backendHost,
        changeOrigin: true,
      },
      '/health': {
        target: backendHost,
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
