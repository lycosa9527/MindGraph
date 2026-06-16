export type SidebarQuoteSource = 'wisdom-quotes-zh' | 'wisdom-quotes-en' | 'echoes-zh' | 'echoes-en'

export interface SidebarQuote {
  id: string
  text: string
  author: string
  source: SidebarQuoteSource
  category?: string
}

export const SIDEBAR_QUOTE_SESSION_KEY = 'sidebar_quote_v1'

/** Pick a new quote after this many ms on the same authenticated page session. */
export const SIDEBAR_QUOTE_ROTATE_MS = 5 * 60 * 1000

export const SIDEBAR_QUOTE_MAX_ZH = 40
export const SIDEBAR_QUOTE_MAX_EN = 120

export function formatSidebarQuoteLine(quote: SidebarQuote): string {
  return formatSidebarQuoteTextAuthor(quote.text, quote.author)
}

export function formatSidebarQuoteTextAuthor(text: string, author = ''): string {
  const trimmedText = text.trim()
  const trimmedAuthor = author.trim()
  if (!trimmedText) {
    return ''
  }
  if (!trimmedAuthor) {
    return trimmedText
  }
  return `${trimmedText} — ${trimmedAuthor}`
}

export function isChineseUiLocale(language: string): boolean {
  return language === 'zh' || language === 'zh-tw'
}
