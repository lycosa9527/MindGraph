import { readFileSync } from 'fs'

import type { SidebarQuote } from '../../src/types/sidebar-quotes.ts'
import { VENDOR_WISDOM_EN, VENDOR_WISDOM_ZH } from './config.ts'
import { buildQuote } from './utils.ts'

interface WisdomChineseLine {
  name?: string
  from?: string
}

interface WisdomEnglishQuote {
  quoteText?: string
  quoteAuthor?: string
}

function parseChineseJsonl(raw: string): WisdomChineseLine[] {
  const lines = raw.split(/\r?\n/).filter((line) => line.trim().length > 0)
  const rows: WisdomChineseLine[] = []
  for (const line of lines) {
    try {
      rows.push(JSON.parse(line) as WisdomChineseLine)
    } catch {
      continue
    }
  }
  return rows
}

export function normalizeWisdomQuotesZhFromFile(path = VENDOR_WISDOM_ZH): SidebarQuote[] {
  const raw = readFileSync(path, 'utf8')
  const lines = parseChineseJsonl(raw)
  const quotes: SidebarQuote[] = []
  for (const line of lines) {
    const text = line.name?.trim() ?? ''
    const author = line.from?.trim() ?? ''
    const quote = buildQuote('wisdom-quotes-zh', text, author)
    if (quote) {
      quotes.push(quote)
    }
  }
  return quotes
}

export function normalizeWisdomQuotesEnFromFile(path = VENDOR_WISDOM_EN): SidebarQuote[] {
  const raw = readFileSync(path, 'utf8')
  const parsed = JSON.parse(raw) as WisdomEnglishQuote[]
  if (!Array.isArray(parsed)) {
    return []
  }
  const quotes: SidebarQuote[] = []
  for (const row of parsed) {
    const text = row.quoteText?.trim() ?? ''
    const author = row.quoteAuthor?.trim() ?? ''
    const quote = buildQuote('wisdom-quotes-en', text, author)
    if (quote) {
      quotes.push(quote)
    }
  }
  return quotes
}
