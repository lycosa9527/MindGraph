import { readFileSync } from 'fs'

import type { SidebarQuote } from '../../src/types/sidebar-quotes.ts'
import { VENDOR_MINDGROWTH_ZH } from './config.ts'
import { buildQuote } from './utils.ts'

interface MindgrowthChineseLine {
  name?: string
  from?: string
  category?: string
}

function parseChineseJsonl(raw: string): MindgrowthChineseLine[] {
  const lines = raw.split(/\r?\n/).filter((line) => line.trim().length > 0)
  const rows: MindgrowthChineseLine[] = []
  for (const line of lines) {
    try {
      rows.push(JSON.parse(line) as MindgrowthChineseLine)
    } catch {
      continue
    }
  }
  return rows
}

export function normalizeMindgrowthQuotesZhFromFile(
  path = VENDOR_MINDGROWTH_ZH
): SidebarQuote[] {
  const raw = readFileSync(path, 'utf8')
  const lines = parseChineseJsonl(raw)
  const quotes: SidebarQuote[] = []
  for (const line of lines) {
    const text = line.name?.trim() ?? ''
    const author = line.from?.trim() ?? ''
    const category = line.category?.trim() ?? ''
    const quote = buildQuote('mindgrowth-zh', text, author, category || undefined)
    if (quote) {
      quotes.push(quote)
    }
  }
  return quotes
}
