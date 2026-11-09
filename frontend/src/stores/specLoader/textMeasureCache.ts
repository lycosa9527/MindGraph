/**
 * Shared home for hidden text measurers, plus a result cache.
 *
 * The host uses `contain: strict`, so reading a measurer lays out only the
 * host, not the whole canvas page. A font finishing its load clears the cache,
 * because the same text then paints at a different width. Results still cache
 * while faces load: a large diagram re-measures the same labels on every size
 * report, and that storm keeps the main thread too busy for the load to finish.
 */

const CACHE_LIMIT = 4000

let containedRoot: HTMLDivElement | null = null
const widthCache = new Map<string, number>()
const boxCache = new Map<string, { width: number; height: number }>()
const clearListeners = new Set<() => void>()
let fontListenerInstalled = false

function installFontListener(): void {
  if (fontListenerInstalled || typeof document === 'undefined' || !document.fonts) return
  fontListenerInstalled = true
  document.fonts.addEventListener('loadingdone', clearTextMeasureCache)
}

function remember<T>(cache: Map<string, T>, key: string, value: T): void {
  if (cache.size >= CACHE_LIMIT) {
    const oldest = cache.keys().next().value
    if (oldest !== undefined) cache.delete(oldest)
  }
  cache.set(key, value)
}

function clearTextMeasureCache(): void {
  widthCache.clear()
  boxCache.clear()
  for (const listener of clearListeners) listener()
}

/** Other width caches that must drop with this one when a font lands. */
export function onTextMeasureCacheClear(listener: () => void): void {
  clearListeners.add(listener)
  installFontListener()
}

/** Contained parent for every hidden measurer; null before `document.body` exists. */
export function containedMeasureRoot(): HTMLDivElement | null {
  if (typeof document === 'undefined' || !document.body) return null
  installFontListener()
  if (containedRoot?.isConnected) return containedRoot
  containedRoot = document.createElement('div')
  containedRoot.setAttribute('aria-hidden', 'true')
  containedRoot.style.cssText = [
    'position:absolute',
    'left:0',
    'top:0',
    'width:0',
    'height:0',
    'overflow:hidden',
    'contain:strict',
    'visibility:hidden',
    'pointer-events:none',
  ].join(';')
  document.body.appendChild(containedRoot)
  return containedRoot
}

export function cachedMeasuredWidth(key: string): number | undefined {
  return widthCache.get(key)
}

export function rememberMeasuredWidth(key: string, width: number): void {
  if (width > 0) remember(widthCache, key, width)
}

export function cachedMeasuredBox(key: string): { width: number; height: number } | undefined {
  return boxCache.get(key)
}

export function rememberMeasuredBox(key: string, box: { width: number; height: number }): void {
  if (box.width > 0 && box.height > 0) remember(boxCache, key, box)
}
