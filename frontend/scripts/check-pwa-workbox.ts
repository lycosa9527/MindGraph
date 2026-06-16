/**
 * CI guard: PWA must not precache every lazy chunk/font (cold-load storm).
 * Shell + icons precache; /assets/* uses runtime CacheFirst after first fetch.
 */
import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
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
  throw new Error('vite.config.ts must define PWA_PRECACHE_GLOB_PATTERNS for shell precache')
}

if (!viteConfig.includes('PWA_RUNTIME_CACHING')) {
  throw new Error('vite.config.ts must define PWA_RUNTIME_CACHING for on-demand /assets/* cache')
}

if (!viteConfig.includes("'**/sidebar-quotes-*'")) {
  throw new Error('vite PWA workbox must globIgnore sidebar-quotes assets')
}

if (!viteConfig.includes("urlPattern: /^\\/assets\\//")) {
  throw new Error('vite PWA runtimeCaching must include /assets/ CacheFirst rule')
}

console.log('PWA workbox config OK (shell precache + runtime /assets cache)')
