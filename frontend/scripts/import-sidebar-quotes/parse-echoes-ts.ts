import { readFileSync, readdirSync } from 'fs'
import { join } from 'path'

import type { SidebarQuote } from '../../src/types/sidebar-quotes.ts'
import { VENDOR_ECHOES_DIR } from './config.ts'
import { buildQuote, unescapeTsString } from './utils.ts'

const NAME_PATTERN = /name:\s*\{\s*en:\s*'((?:\\'|[^'])*)',\s*zh:\s*'((?:\\'|[^'])*)',/s
const TEXT_PATTERN = /text:\s*\{\s*en:\s*'((?:\\'|[^'])*)',\s*zh:\s*'((?:\\'|[^'])*)',/gs

function categoryFromFilename(filename: string): string {
  return filename.replace(/\.ts$/, '')
}

export function parseEchoesFromVendorTs(dir = VENDOR_ECHOES_DIR): {
  zh: SidebarQuote[]
  en: SidebarQuote[]
} {
  const zh: SidebarQuote[] = []
  const en: SidebarQuote[] = []
  let files: string[]
  try {
    files = readdirSync(dir).filter((name) => name.endsWith('.ts'))
  } catch {
    return { zh, en }
  }

  for (const filename of files) {
    const category = categoryFromFilename(filename)
    const content = readFileSync(join(dir, filename), 'utf8')
    const slugBlocks = content.split(/\n\s*slug:\s*'/).slice(1)
    for (const block of slugBlocks) {
      const nameMatch = block.match(NAME_PATTERN)
      const authorEn = nameMatch ? unescapeTsString(nameMatch[1]) : ''
      const authorZh = nameMatch ? unescapeTsString(nameMatch[2]) : authorEn

      for (const textMatch of block.matchAll(TEXT_PATTERN)) {
        const textEn = unescapeTsString(textMatch[1])
        const textZh = unescapeTsString(textMatch[2])
        const zhQuote = buildQuote('echoes-zh', textZh, authorZh, category)
        const enQuote = buildQuote('echoes-en', textEn, authorEn, category)
        if (zhQuote) {
          zh.push(zhQuote)
        }
        if (enQuote) {
          en.push(enQuote)
        }
      }
    }
  }

  return { zh, en }
}
