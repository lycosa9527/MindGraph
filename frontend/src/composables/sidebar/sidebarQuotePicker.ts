import type { SidebarQuote } from '@/types/sidebar-quotes'
import {
  SIDEBAR_QUOTE_ROTATE_MS,
  SIDEBAR_QUOTE_SESSION_KEY,
  formatSidebarQuoteLine,
  isChineseUiLocale,
} from '@/types/sidebar-quotes'

export interface SidebarQuoteSessionCache {
  id: string
  /** Epoch ms when the current quote was first shown in this browser tab. */
  shownAt?: number
}

export type SidebarQuoteLocaleBucket = 'zh' | 'en'

let sidebarQuoteHydratedThisPage = false
let sidebarQuoteActiveUserId: string | null = null

export function resetSidebarQuotePageSession(): void {
  sidebarQuoteHydratedThisPage = false
}

export function resetSidebarQuoteSessionState(): void {
  sidebarQuoteHydratedThisPage = false
  sidebarQuoteActiveUserId = null
}

export function isSidebarQuoteHydratedThisPage(): boolean {
  return sidebarQuoteHydratedThisPage
}

export function markSidebarQuoteHydratedThisPage(): void {
  sidebarQuoteHydratedThisPage = true
}

export function detectSidebarQuoteUserLogin(userId: string): boolean {
  return sidebarQuoteActiveUserId !== userId
}

export function rememberSidebarQuoteUser(userId: string): void {
  sidebarQuoteActiveUserId = userId
}

export function quoteLocaleBucket(language: string): SidebarQuoteLocaleBucket {
  return isChineseUiLocale(language) ? 'zh' : 'en'
}

export function readQuoteSessionCache(
  key = SIDEBAR_QUOTE_SESSION_KEY
): SidebarQuoteSessionCache | null {
  if (typeof sessionStorage === 'undefined') {
    return null
  }
  const raw = sessionStorage.getItem(key)
  if (!raw) {
    return null
  }
  try {
    const parsed = JSON.parse(raw) as SidebarQuoteSessionCache
    if (typeof parsed.id === 'string' && parsed.id.length > 0) {
      const shownAt =
        typeof parsed.shownAt === 'number' && Number.isFinite(parsed.shownAt)
          ? parsed.shownAt
          : undefined
      return shownAt === undefined ? { id: parsed.id } : { id: parsed.id, shownAt }
    }
  } catch {
    return null
  }
  return null
}

export function writeQuoteSessionCache(
  cache: SidebarQuoteSessionCache,
  key = SIDEBAR_QUOTE_SESSION_KEY
): void {
  if (typeof sessionStorage === 'undefined') {
    return
  }
  sessionStorage.setItem(key, JSON.stringify(cache))
}

export function clearQuoteSessionCache(key = SIDEBAR_QUOTE_SESSION_KEY): void {
  if (typeof sessionStorage === 'undefined') {
    return
  }
  sessionStorage.removeItem(key)
}

export function remainingQuoteRotateMs(
  shownAt: number | undefined,
  now = Date.now(),
  rotateMs = SIDEBAR_QUOTE_ROTATE_MS
): number {
  if (shownAt == null || !Number.isFinite(shownAt)) {
    return rotateMs
  }
  return Math.max(0, rotateMs - (now - shownAt))
}

export function quoteSessionShownAt(
  cache: SidebarQuoteSessionCache | null,
  now = Date.now()
): number {
  if (cache?.shownAt != null && Number.isFinite(cache.shownAt)) {
    return cache.shownAt
  }
  return now
}

export function writeQuoteSessionForPick(
  quote: SidebarQuote,
  options: { forceNew: boolean; now?: number }
): SidebarQuoteSessionCache {
  const now = options.now ?? Date.now()
  const existing = readQuoteSessionCache()
  const keepShownAt = !options.forceNew && existing?.id === quote.id && existing.shownAt != null
  const cache: SidebarQuoteSessionCache = {
    id: quote.id,
    shownAt: keepShownAt ? existing.shownAt : now,
  }
  writeQuoteSessionCache(cache)
  return cache
}

export function findQuoteById(quotes: SidebarQuote[], id: string): SidebarQuote | undefined {
  return quotes.find((quote) => quote.id === id)
}

export function pickRandomQuote(quotes: SidebarQuote[]): SidebarQuote | null {
  if (quotes.length === 0) {
    return null
  }
  const index = Math.floor(Math.random() * quotes.length)
  return quotes[index] ?? null
}

export function pickRandomQuoteExcluding(
  quotes: SidebarQuote[],
  excludeId: string | null | undefined,
  random = Math.random
): SidebarQuote | null {
  if (quotes.length === 0) {
    return null
  }
  if (!excludeId || quotes.length === 1) {
    const picked = pickRandomQuote(quotes)
    if (picked) {
      markSidebarQuoteHydratedThisPage()
    }
    return picked
  }
  const candidates = quotes.filter((quote) => quote.id !== excludeId)
  const pool = candidates.length > 0 ? candidates : quotes
  const index = Math.floor(random() * pool.length)
  const picked = pool[index] ?? null
  if (picked) {
    markSidebarQuoteHydratedThisPage()
  }
  return picked
}

export function preferQuotesWithAuthor(pool: SidebarQuote[]): SidebarQuote[] {
  const withAuthor = pool.filter((row) => row.author.trim().length > 0)
  return withAuthor.length > 0 ? withAuthor : pool
}

export function resolveSidebarQuote(
  quotes: SidebarQuote[],
  cachedId: string | null,
  random = Math.random
): SidebarQuote | null {
  if (quotes.length === 0) {
    return null
  }
  if (isSidebarQuoteHydratedThisPage() && cachedId) {
    const cached = findQuoteById(quotes, cachedId)
    if (cached) {
      return cached
    }
  }
  const index = Math.floor(random() * quotes.length)
  const picked = quotes[index] ?? null
  if (picked) {
    markSidebarQuoteHydratedThisPage()
  }
  return picked
}

export function formatQuoteDisplayLine(quote: SidebarQuote | null): string {
  if (!quote) {
    return ''
  }
  return formatSidebarQuoteLine(quote)
}

const quotePoolCache: Partial<Record<SidebarQuoteLocaleBucket, SidebarQuote[]>> = {}

export function resetSidebarQuotePoolCache(): void {
  delete quotePoolCache.zh
  delete quotePoolCache.en
}

async function fetchSidebarQuotePool(url: string): Promise<SidebarQuote[]> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to load sidebar quotes (${response.status})`)
  }
  const rows = (await response.json()) as SidebarQuote[]
  if (!Array.isArray(rows)) {
    throw new Error('Invalid sidebar quote pool payload')
  }
  return rows
}

export async function loadSidebarQuotePool(
  bucket: SidebarQuoteLocaleBucket
): Promise<SidebarQuote[]> {
  const cached = quotePoolCache[bucket]
  if (cached) {
    return cached
  }

  if (bucket === 'zh') {
    const { default: url } = await import('@/assets/sidebar-quotes-zh.json?url')
    const rows = await fetchSidebarQuotePool(url)
    quotePoolCache[bucket] = rows
    return rows
  }
  const { default: url } = await import('@/assets/sidebar-quotes-en.json?url')
  const rows = await fetchSidebarQuotePool(url)
  quotePoolCache[bucket] = rows
  return rows
}
