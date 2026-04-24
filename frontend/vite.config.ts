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
      // Rolldown production builds mishandle lucide-vue-next's per-icon ESM files
      // (`export { createLucideIcon as default }`), breaking `npm run preview` / deploy.
      // Single CJS bundle matches dev (esbuild prebundle) interop; see lucide#2087.
      'lucide-vue-next': resolve(
        __dirname,
        'node_modules/lucide-vue-next/dist/cjs/lucide-vue-next.js'
      ),
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
    // Element Plus + icons is ~1.2MB minified. Let Rolldown choose shared chunks:
    // manual vendor grouping caused production-only interop failures where minified
    // imports such as `dt(...)` were not callable in preview/deploy builds.
    chunkSizeWarningLimit: 1300,
  },
})
