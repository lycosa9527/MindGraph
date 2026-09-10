/**
 * Load MathLive for 插入公式.
 *
 * Bare `import('mathlive')` is rewritten to Vite's optimized dep
 * `/node_modules/.vite/deps/mathlive.js?v=…`. That fetch 404s/504s when the
 * dep cache is stale (old WSL `/mnt/c` path) or still prebundles the 1.5MB
 * development `mathlive.mjs`. The Vite alias pins the bare specifier to
 * `mathlive.min.mjs` and optimizeDeps excludes it so this import is served
 * from `node_modules` instead of the deps cache.
 */
type MathLiveModule = {
  MathfieldElement?: { locale: string }
}

export async function loadMathLive(): Promise<MathLiveModule> {
  const [mod] = await Promise.all([import('mathlive'), import('mathlive/fonts.css')])
  return mod as MathLiveModule
}
