/**
 * CI guard: PWA must not precache every lazy chunk/font (cold-load storm).
 * Icons precache; the HTML shell stays on the network so the CSP nonce stays fresh.
 * /assets/* uses runtime CacheFirst after first fetch.
 */
import { readFileSync } from 'fs'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const viteConfigPath = resolve(frontendDir, 'vite.config.ts')
const viteConfig = readFileSync(viteConfigPath, 'utf8')

if (viteConfig.includes("'**/*.{js,css,html,ico,png,svg,woff2,woff,webmanifest}'")) {
  throw new Error(
    'vite PWA workbox globPatterns must not precache all JS/CSS/fonts; use PWA_PRECACHE_GLOB_PATTERNS'
  )
}

if (!viteConfig.includes('PWA_PRECACHE_GLOB_PATTERNS')) {
  throw new Error('vite.config.ts must define PWA_PRECACHE_GLOB_PATTERNS for icon precache')
}

if (!viteConfig.includes('PWA_RUNTIME_CACHING')) {
  throw new Error('vite.config.ts must define PWA_RUNTIME_CACHING for on-demand /assets/* cache')
}

if (!viteConfig.includes("'**/sidebar-quotes-*'")) {
  throw new Error('vite PWA workbox must globIgnore sidebar-quotes assets')
}

if (!viteConfig.includes("'**/training/roles/**'")) {
  throw new Error('vite PWA workbox must globIgnore packed role WebPs (COS catalog)')
}

if (!viteConfig.includes('urlPattern: /^\\/assets\\//')) {
  throw new Error('vite PWA runtimeCaching must include /assets/ CacheFirst rule')
}

if (viteConfig.includes('navigateFallback:')) {
  throw new Error(
    'vite PWA must not set navigateFallback; a precached shell freezes the CSP nonce and VOD hosts'
  )
}

if (/PWA_PRECACHE_GLOB_PATTERNS = \[[\s\S]*?'index\.html'/.test(viteConfig)) {
  throw new Error('vite PWA precache must not include index.html (per-request CSP)')
}

console.log('PWA workbox config OK (icon precache + network document + runtime /assets cache)')
