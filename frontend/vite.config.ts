import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
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

const elementPlusResolver = ElementPlusResolver({
  importStyle: 'css',
})

export default defineConfig({
  optimizeDeps: {
    include: [
      'markdown-it',
      '@vscode/markdown-it-katex',
      'katex',
      'katex/contrib/mhchem',
      'dompurify',
      'lucide-vue-next',
      'mathlive',
      '@tanstack/vue-query',
      '@vueuse/core',
      'vue-demi',
    ],
  },
  plugins: [
    vue({
      template: {
        compilerOptions: {
          isCustomElement: (tag) => tag === 'math-field',
        },
      },
    }),
    tailwindcss(),
    AutoImport({
      dts: 'src/auto-imports.d.ts',
      resolvers: [elementPlusResolver],
    }),
    Components({
      dts: 'src/components.d.ts',
      resolvers: [elementPlusResolver],
    }),
  ],
  define: {
    __APP_VERSION__: JSON.stringify(version),
    __BUILD_TIME__: JSON.stringify(Date.now()),
  },
  resolve: {
    // tsconfig `paths` for TS/JS; explicit `@` alias still required for CSS @import in SFCs
    // (Tailwind generate / enhanced-resolve does not resolve tsconfigPaths for those).
    tsconfigPaths: true,
    // One KaTeX instance so `katex/contrib/mhchem` registers `\ce` on the same copy used by @vscode/markdown-it-katex.
    dedupe: ['katex', 'vue', 'vue-demi'],
    alias: {
      '@': resolve(__dirname, 'src'),
      '@data': resolve(__dirname, '../data'),
    },
  },
  server: {
    // Use 41732+ to avoid ip_unprivileged_port_start (often 32768 on WSL); override with PORT=3000 npm run dev
    port: Number(process.env.PORT) || 41732,
    host: process.env.VITE_HOST || '0.0.0.0',
    strictPort: false,
    proxy: {
      '/api': {
        target: backendHost,
        changeOrigin: true,
        // Workshop chat: browser opens ws(s)://dev-host/api/ws/chat — must upgrade through this proxy
        ws: true,
      },
      '/thinking_mode': {
        target: backendHost,
        changeOrigin: true,
        timeout: 0, // SSE streams: prevent proxy from buffering/closing long-lived connections
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
    // Vite’s default 500 kB is aggressive for feature-rich SPAs; 1000 kB is a
    // practical bar once vendors are split (below). Revisit if a single chunk
    // still exceeds this — prefer more `manualChunks` over raising the limit.
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      onwarn(warning, defaultHandler) {
        // @tailwindcss/vite transforms CSS chunks without emitting sourcemaps;
        // the resulting SOURCEMAP_BROKEN noise is cosmetic — suppress it.
        if (warning.plugin === '@tailwindcss/vite:generate:build') return
        defaultHandler(warning)
      },
      output: {
        /**
         * App routes already use dynamic import() (see `src/router/index.ts`).
         * Splits here isolate large `node_modules` for caching and to avoid a
         * single >1.3 MB vendor blob (notably: Element Plus, icons, echarts, …).
         * Order: more specific sub-packages before broader matches.
         */
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined
          }
          if (id.includes('node_modules/@element-plus/icons-vue')) {
            return 'vendor-ep-icons'
          }
          if (id.includes('node_modules/element-plus') || id.includes('node_modules/@element-plus')) {
            return 'vendor-element-plus'
          }
          if (id.includes('node_modules/echarts')) {
            return 'vendor-echarts'
          }
          if (id.includes('node_modules/chart.js')) {
            return 'vendor-chartjs'
          }
          if (id.includes('node_modules/@vue-flow')) {
            return 'vendor-vue-flow'
          }
          if (id.includes('node_modules/lucide-vue-next')) {
            return 'vendor-lucide'
          }
          if (id.includes('node_modules/katex')) {
            return 'vendor-katex'
          }
          if (id.includes('node_modules/highlight.js')) {
            return 'vendor-highlight'
          }
          if (id.includes('node_modules/mathlive')) {
            return 'vendor-mathlive'
          }
          if (id.includes('node_modules/jspdf')) {
            return 'vendor-jspdf'
          }
          if (
            id.includes('node_modules/markdown-it') ||
            id.includes('node_modules/@vscode/markdown-it-katex') ||
            id.includes('node_modules/dompurify')
          ) {
            return 'vendor-markdown'
          }
          if (id.includes('node_modules/html-to-image')) {
            return 'vendor-html-to-image'
          }
          if (id.includes('node_modules/vue-i18n') || id.includes('node_modules/@intlify')) {
            return 'vendor-i18n'
          }
          if (id.includes('node_modules/@vueuse')) {
            return 'vendor-vueuse'
          }
          if (id.includes('node_modules/@tanstack')) {
            return 'vendor-tanstack'
          }
          if (id.includes('node_modules/simple-keyboard') || id.includes('node_modules/simple-keyboard-layouts')) {
            return 'vendor-keyboard'
          }
          if (id.includes('node_modules/axios')) {
            return 'vendor-axios'
          }
          return undefined
        },
      },
    },
  },
})
