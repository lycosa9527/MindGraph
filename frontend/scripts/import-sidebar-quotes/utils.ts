import { createHash } from 'crypto'

import {
  SIDEBAR_QUOTE_MAX_EN,
  SIDEBAR_QUOTE_MAX_ZH,
  type SidebarQuote,
  type SidebarQuoteSource,
} from '../../src/types/sidebar-quotes.ts'

const BLOCKED_AUTHOR_PATTERN = /张雪峰/

export function unescapeTsString(value: string): string {
  return value
    .replace(/\\'/g, "'")
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\\\/g, '\\')
}

export function graphemeLength(text: string): number {
  return [...text].length
}

export function isWithinMaxLength(text: string, locale: 'zh' | 'en'): boolean {
  const max = locale === 'zh' ? SIDEBAR_QUOTE_MAX_ZH : SIDEBAR_QUOTE_MAX_EN
  return graphemeLength(text) <= max
}

export function normalizeDedupeKey(text: string, locale: 'zh' | 'en'): string {
  const trimmed = text.trim()
  if (locale === 'en') {
    return trimmed.toLowerCase()
  }
  return trimmed
}

export function makeQuoteId(source: SidebarQuoteSource, text: string, author: string): string {
  const hash = createHash('sha1').update(`${source}|${text}|${author}`).digest('hex').slice(0, 12)
  return `${source}:${hash}`
}

export function isBlockedQuote(text: string, author: string): boolean {
  return BLOCKED_AUTHOR_PATTERN.test(text) || BLOCKED_AUTHOR_PATTERN.test(author)
}

export function buildQuote(
  source: SidebarQuoteSource,
  text: string,
  author: string,
  category?: string
): SidebarQuote | null {
  const trimmedText = text.trim()
  const trimmedAuthor = author.trim()
  if (!trimmedText || isBlockedQuote(trimmedText, trimmedAuthor)) {
    return null
  }
  const locale = source.endsWith('-zh') ? 'zh' : 'en'
  if (!isWithinMaxLength(trimmedText, locale)) {
    return null
  }
  return {
    id: makeQuoteId(source, trimmedText, trimmedAuthor),
    text: trimmedText,
    author: trimmedAuthor,
    source,
    ...(category ? { category } : {}),
  }
}

export function dedupeQuotes(quotes: SidebarQuote[], locale: 'zh' | 'en'): SidebarQuote[] {
  const seen = new Set<string>()
  const result: SidebarQuote[] = []
  for (const quote of quotes) {
    const key = normalizeDedupeKey(quote.text, locale)
    if (seen.has(key)) {
      continue
    }
    seen.add(key)
    result.push(quote)
  }
  return result
}
