import { readFileSync } from 'fs'

import type { SidebarQuote } from '../../src/types/sidebar-quotes.ts'
import { EXTRACTED_ECHOES_EN, EXTRACTED_ECHOES_ZH } from './config.ts'

function readExtractedQuotes(path: string): SidebarQuote[] {
  const raw = readFileSync(path, 'utf8')
  const parsed = JSON.parse(raw) as SidebarQuote[]
  if (!Array.isArray(parsed)) {
    throw new Error(`Extracted echoes file is not a JSON array: ${path}`)
  }
  return parsed
}

export function normalizeEchoesFromExtracted(
  zhPath = EXTRACTED_ECHOES_ZH,
  enPath = EXTRACTED_ECHOES_EN
): { zh: SidebarQuote[]; en: SidebarQuote[] } {
  return {
    zh: readExtractedQuotes(zhPath),
    en: readExtractedQuotes(enPath),
  }
}
