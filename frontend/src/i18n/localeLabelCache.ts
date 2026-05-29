/**
 * Callback registry for diagram default-label caches.
 * Keeps i18n free of imports from diagram stores (avoids circular deps).
 */

const invalidators = new Set<() => void>()

export function registerLocaleLabelCacheInvalidator(fn: () => void): () => void {
  invalidators.add(fn)
  return () => {
    invalidators.delete(fn)
  }
}

export function notifyLocaleLoaded(): void {
  for (const fn of invalidators) {
    fn()
  }
}
