import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { homedir } from 'os'
import { resolve, dirname, join } from 'path'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { VitePWA } from 'vite-plugin-pwa'
import { visualizer } from 'rollup-plugin-visualizer'

const __dirname = dirname(fileURLToPath(import.meta.url))

/** WSL projects on /mnt/c often hit EACCES when Vite renames deps_temp → deps under node_modules/.vite. */
function resolveCacheDir(projectRoot: string): string {
  const override = process.env.VITE_CACHE_DIR?.trim()
  if (override) {
    return resolve(override)
  }
  if (process.platform === 'linux' && projectRoot.startsWith('/mnt/')) {
    return join(homedir(), '.cache', 'mindgraph-vite')
  }
  return join(projectRoot, 'node_modules', '.vite')
}

const cacheDir = resolveCacheDir(__dirname)

const devPort = Number(process.env.PORT) || 41732
const devHost = process.env.VITE_HOST || '0.0.0.0'

/**
 * HMR WebSocket target. With `host: 0.0.0.0`, Vite 8 still injects `ws://0.0.0.0`
 * unless `server.hmr.host` is set — browsers cannot connect and updates never apply.
 * Same-machine dev: defaults to localhost. LAN/phone testing: set `VITE_HMR_HOST`.
 */
function resolveHmrConfig(port: number, host: string | boolean) {
  const explicitHost = process.env.VITE_HMR_HOST?.trim()
  const explicitPort = process.env.VITE_HMR_PORT?.trim()
  const explicitClientPort = process.env.VITE_HMR_CLIENT_PORT?.trim()
  if (explicitHost || explicitPort || explicitClientPort) {
    return {
      ...(explicitHost ? { host: explicitHost } : {}),
      ...(explicitPort ? { port: Number(explicitPort) } : {}),
      ...(explicitClientPort ? { clientPort: Number(explicitClientPort) } : {}),
    }
  }
  const bindAll =
    host === true || host === 'true' || host === '0.0.0.0' || host === '::'
  if (!bindAll) {
    return undefined
  }
  return {
    host: 'localhost',
    port,
    clientPort: port,
  }
}

/** WSL edits on `/mnt/c` from Windows apps do not emit inotify events without polling. */
function resolveWatchConfig(projectRoot: string) {
  const flag = process.env.VITE_USE_POLLING?.trim().toLowerCase()
  const explicit = flag === '1' || flag === 'true'
  const onWslWindowsMount =
    process.platform === 'linux' && projectRoot.startsWith('/mnt/')
  if (!explicit && !onWslWindowsMount) {
    return undefined
  }
  const interval = Number(process.env.VITE_POLL_INTERVAL)
  return {
    usePolling: true,
    interval: Number.isFinite(interval) && interval > 0 ? interval : 1000,
  }
}

const devHmr = resolveHmrConfig(devPort, devHost)
const devWatch = resolveWatchConfig(__dirname)
const isPwaDev = process.env.VITE_PWA_DEV === '1'

/** Precache shell + icons only; lazy chunks/fonts load on demand (runtime cache below). */
const PWA_PRECACHE_GLOB_PATTERNS = [
  'index.html',
  '**/*.{ico,png,svg,webmanifest}',
  'favicon.svg',
  'robots.txt',
  'apple-touch-icon.png',
  'pwa-*.png',
]

/** Cache hashed bundles after first network fetch (offline repeat visits). */
const PWA_RUNTIME_CACHING = [
  {
    urlPattern: /^\/assets\//,
    handler: 'CacheFirst' as const,
    options: {
      cacheName: 'mindgraph-assets',
      expiration: {
        maxEntries: 500,
        maxAgeSeconds: 60 * 60 * 24 * 365,
      },
      cacheableResponse: {
        statuses: [0, 200],
      },
    },
  },
  {
    urlPattern: /^\/gallery\//,
    handler: 'CacheFirst' as const,
    options: {
      cacheName: 'mindgraph-gallery',
      expiration: {
        maxEntries: 100,
        maxAgeSeconds: 60 * 60 * 24 * 30,
      },
      cacheableResponse: {
        statuses: [0, 200],
      },
    },
  },
]

// Read version from VERSION file (single source of truth)
const version = readFileSync(resolve(__dirname, '../VERSION'), 'utf-8').trim()

// Get backend host from environment variable (for WSL/remote scenarios)
// Default to localhost for normal development
// For WSL: Use Windows host IP (e.g., VITE_BACKEND_HOST=http://172.x.x.x:9527)
const backendHost = process.env.VITE_BACKEND_HOST || 'http://localhost:9527'
const backendHostWs = backendHost.replace('http://', 'ws://').replace('https://', 'wss://')
/** Origin header sent to the API on proxied WebSocket upgrades (Host must align; see node-http-proxy + changeOrigin). */
const backendOrigin = backendHost.replace(/\/$/, '')

const elementPlusResolver = ElementPlusResolver({
  importStyle: 'css',
})

/** Dev-only: inject WSL/custom API origin into CSP when VITE_BACKEND_HOST is not localhost:9527. */
function devCspConnectSrcPlugin(apiOrigin: string): Plugin {
  return {
    name: 'mindgraph-dev-csp-connect-src',
    apply: 'serve',
    transformIndexHtml(html) {
      if (
        apiOrigin === 'http://localhost:9527' ||
        apiOrigin === 'http://127.0.0.1:9527' ||
        html.includes(apiOrigin)
      ) {
        return html
      }
      let updated = html.replace(/connect-src ([^;]+)/, `connect-src $1 ${apiOrigin}`)
      if (html.includes('media-src')) {
        updated = updated.replace(/media-src ([^;]+)/, `media-src $1 ${apiOrigin}`)
      }
      return updated
    },
  }
}

export default defineConfig({
  cacheDir,
  optimizeDeps: {
    include: [
      'markdown-it',
      '@vscode/markdown-it-katex',
      'katex',
      'katex/contrib/mhchem',
      'dompurify',
      '@lucide/vue',
      'mathlive',
      '@tanstack/vue-query',
      '@vueuse/core',
      'vue-demi',
      'pdfjs-dist',
    ],
  },
  plugins: [
    devCspConnectSrcPlugin(backendOrigin),
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
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'robots.txt', 'apple-touch-icon.png'],
      manifest: {
        name: 'MindGraph',
        short_name: 'MindGraph',
        description: 'AI-powered mind mapping and teaching platform',
        lang: 'en',
        dir: 'ltr',
        theme_color: '#1c1917',
        background_color: '#1c1917',
        display: 'standalone',
        display_override: ['standalone', 'minimal-ui'],
        orientation: 'any',
        prefer_related_applications: false,
        categories: ['education', 'productivity'],
        start_url: '/',
        scope: '/',
        id: '/',
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        globPatterns: isPwaDev ? [] : PWA_PRECACHE_GLOB_PATTERNS,
        // Sidebar quote pools are fetched on demand after login (locale-specific).
        globIgnores: ['**/sidebar-quotes-*', '**/stats.html'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [
          /^\/api/,
          /^\/ws/,
          /^\/static/,
          /^\/health/,
          /^\/thinking_mode/,
        ],
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
        runtimeCaching: isPwaDev ? undefined : PWA_RUNTIME_CACHING,
      },
      devOptions: {
        enabled: isPwaDev,
        suppressWarnings: isPwaDev,
      },
    }),
    ...(process.env.ANALYZE === '1'
      ? [
          visualizer({
            filename: 'dist/stats.html',
            gzipSize: true,
            open: true,
          }),
        ]
      : []),
  ],
  define: {
    __APP_VERSION__: JSON.stringify(version),
    __BUILD_TIME__: JSON.stringify(Date.now()),
    __DEV_API_ORIGIN__: JSON.stringify(
      process.env.NODE_ENV === 'production' ? '' : backendHost.replace(/\/$/, '')
    ),
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
    port: devPort,
    // 0.0.0.0: Vite prints Local + several Network URLs on WSL (LAN IP + 172.x Docker/Hyper-V bridges).
    // - Browser on same Windows host: prefer http://localhost:41732 (auto-forward to WSL2 on recent Windows).
    // - Phone / another PC on Wi‑Fi: use the real LAN line (e.g. http://192.168.x.x:41732), not the 172.* bridges.
    //   Set VITE_HMR_HOST to that LAN IP so the HMR WebSocket matches the page origin.
    host: devHost,
    strictPort: false,
    ...(devHmr ? { hmr: devHmr } : {}),
    ...(devWatch ? { watch: devWatch } : {}),
    proxy: {
      '/api': {
        target: backendHost,
        changeOrigin: true,
        // Workshop chat + canvas-asr: browser opens ws(s)://dev-host/api/ws/...
        ws: true,
        // Long-lived WS/SSE: avoid proxy closing idle connections too eagerly
        timeout: 0,
        proxyTimeout: 0,
        configure: (proxy) => {
          proxy.on('error', (err: NodeJS.ErrnoException) => {
            const code = err?.code
            if (code === 'ECONNABORTED' || code === 'ECONNRESET' || code === 'EPIPE') {
              return
            }
            console.error('[vite proxy /api]', err)
          })
          // changeOrigin does not rewrite Origin on WS upgrades (http-proxy). LAN pages send
          // Origin: http://192.168.x.x:41732 while the upstream target is localhost:9527 — some
          // stacks treat that as a mismatch. Align Origin with the API base URL.
          proxy.on('proxyReqWs', (proxyReq, _req, socket) => {
            proxyReq.setHeader('origin', backendOrigin)
            socket.on('error', () => {
              /* peer closed during WebSocket upgrade or teardown */
            })
          })
        },
      },
      '/thinking_mode': {
        target: backendHost,
        changeOrigin: true,
        timeout: 0, // SSE streams: prevent proxy from buffering/closing long-lived connections
      },
      '/ws': {
        target: backendHostWs,
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
          proxy.on('proxyReqWs', (proxyReq, _req, socket) => {
            proxyReq.setHeader('origin', backendOrigin)
            socket.on('error', () => {
              /* same Origin alignment as /api WS proxy */
            })
          })
        },
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
    sourcemap: process.env.SOURCEMAP === '1' ? true : false,
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
         * Splits here isolate large non-EP `node_modules` for caching (icons,
         * echarts, …). Element Plus is NOT force-chunked: a former catch-all
         * `vendor-ep-core` / data+overlay split pulled heavy widgets into the
         * entry graph via cross-chunk static imports. EP loads via deep ESM
         * paths + deferred overlay helpers (`notifications.ts`) and Rollup
         * places the rest with the routes that import them.
         * Order: more specific sub-packages before broader matches.
         */
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined
          }
          if (id.includes('node_modules/@element-plus/icons-vue')) {
            return 'vendor-ep-icons'
          }
          // Do not force-chunk echarts/jspdf: they are only used from route-level
          // code (dynamic import / lazy pages). Naming them via manualChunks caused
          // Rolldown to static-import those chunks from the entry for sharing.
          if (id.includes('node_modules/chart.js')) {
            return 'vendor-chartjs'
          }
          if (id.includes('node_modules/@vue-flow')) {
            return 'vendor-vue-flow'
          }
          if (id.includes('node_modules/@lucide/vue')) {
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
          if (id.includes('node_modules/simple-keyboard') && !id.includes('simple-keyboard-layouts')) {
            return 'vendor-keyboard'
          }
          return undefined
        },
      },
    },
  },
})
