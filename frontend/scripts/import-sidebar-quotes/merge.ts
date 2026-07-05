import { mkdirSync, readFileSync, writeFileSync } from 'fs'
import { dirname } from 'path'

import type { SidebarQuote } from '../../src/types/sidebar-quotes.ts'
import {
  ATTRIBUTIONS_PATH,
  ECHOES_REF,
  ECHOES_REPO,
  EXTRACTED_ECHOES_MANIFEST,
  MIN_EN_QUOTES,
  MIN_ZH_QUOTES,
  OUTPUT_EN,
  OUTPUT_ZH,
  WISDOM_QUOTES_REF,
  WISDOM_QUOTES_REPO,
} from './config.ts'
import { normalizeEchoesFromExtracted } from './normalize-echoes.ts'
import { normalizeMindgrowthQuotesZhFromFile } from './normalize-mindgrowth.ts'
import {
  normalizeWisdomQuotesEnFromFile,
  normalizeWisdomQuotesZhFromFile,
} from './normalize-wisdom-quotes.ts'
import { dedupeQuotes } from './utils.ts'

interface EchoesExtractManifest {
  source?: { repo?: string; ref?: string; license?: string }
  extractedAt?: string
}

function readEchoesManifest(): EchoesExtractManifest {
  const raw = readFileSync(EXTRACTED_ECHOES_MANIFEST, 'utf8')
  return JSON.parse(raw) as EchoesExtractManifest
}

function buildAttributionsContent(manifest: EchoesExtractManifest): string {
  const extractedAt = manifest.extractedAt ?? 'unknown'
  return `# Sidebar quote library — attributions

## snakeek/wisdom-quotes

- Repository: https://github.com/${WISDOM_QUOTES_REPO}
- Pinned ref: \`${WISDOM_QUOTES_REF}\`
- License: MIT OR Apache-2.0 (tool)
- Files: \`chinese_sentences.json\`, \`quotes_database.json\`
- Upstream Chinese data: https://github.com/caoxingyu/chinese-gushiwen
- Upstream English data: https://github.com/JamesFT/Database-Quotes-JSON

## Luminoid/echoes (frozen extract)

- Original repository: https://github.com/${ECHOES_REPO}
- Source ref at extract: \`${ECHOES_REF}\`
- Extracted at: \`${extractedAt}\`
- Shipped as: \`scripts/vendor/sidebar-quotes/extracted/echoes-zh.json\`,
  \`echoes-en.json\` (no live upstream fetch at import/build)
- License: **CC BY-NC-SA 4.0**
- **Commercial use:** confirm with product owner before shipping echoes-derived lines
  in a commercial product, or remove the extracted echoes JSON from vendor/.

## MindGraph curated (mindgrowth)

- Source: \`scripts/vendor/sidebar-quotes/mindgraph/mindgrowth-quotes-zh.jsonl\`
- Curated Chinese quotes on thinking, learning, education, and personal growth
- Categories: \`thinking\`, \`learning\`, \`education\`, \`growth\`

## MindGraph

- Import script: \`frontend/scripts/import-sidebar-quotes/\`
- Output: \`frontend/src/assets/sidebar-quotes-zh.json\`,
  \`frontend/src/assets/sidebar-quotes-en.json\`
`
}

function assertMinimumCounts(zhCount: number, enCount: number): void {
  if (zhCount < MIN_ZH_QUOTES) {
    throw new Error(`Expected at least ${MIN_ZH_QUOTES} zh quotes, got ${zhCount}`)
  }
  if (enCount < MIN_EN_QUOTES) {
    throw new Error(`Expected at least ${MIN_EN_QUOTES} en quotes, got ${enCount}`)
  }
}

function validateQuoteRows(quotes: SidebarQuote[], locale: 'zh' | 'en'): void {
  for (const quote of quotes) {
    if (!quote.id || !quote.text.trim()) {
      throw new Error(`Invalid ${locale} quote row: missing id or text`)
    }
  }
}

function writeJson(path: string, quotes: SidebarQuote[]): void {
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, JSON.stringify(quotes), 'utf8')
}

export function runImport(): { zhCount: number; enCount: number } {
  const mindgrowthZh = normalizeMindgrowthQuotesZhFromFile()
  const wisdomZh = normalizeWisdomQuotesZhFromFile()
  const wisdomEn = normalizeWisdomQuotesEnFromFile()
  const echoes = normalizeEchoesFromExtracted()
  const manifest = readEchoesManifest()

  const zhQuotes = dedupeQuotes([...mindgrowthZh, ...wisdomZh, ...echoes.zh], 'zh')
  const enQuotes = dedupeQuotes([...wisdomEn, ...echoes.en], 'en')

  validateQuoteRows(zhQuotes, 'zh')
  validateQuoteRows(enQuotes, 'en')
  assertMinimumCounts(zhQuotes.length, enQuotes.length)

  writeJson(OUTPUT_ZH, zhQuotes)
  writeJson(OUTPUT_EN, enQuotes)
  mkdirSync(dirname(ATTRIBUTIONS_PATH), { recursive: true })
  writeFileSync(ATTRIBUTIONS_PATH, buildAttributionsContent(manifest), 'utf8')

  return { zhCount: zhQuotes.length, enCount: enQuotes.length }
}
