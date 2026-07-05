import { describe, expect, it } from 'vitest'

import { runImport } from '../scripts/import-sidebar-quotes/merge.ts'
import { normalizeEchoesFromExtracted } from '../scripts/import-sidebar-quotes/normalize-echoes.ts'
import { normalizeMindgrowthQuotesZhFromFile } from '../scripts/import-sidebar-quotes/normalize-mindgrowth.ts'
import {
  normalizeWisdomQuotesEnFromFile,
  normalizeWisdomQuotesZhFromFile,
} from '../scripts/import-sidebar-quotes/normalize-wisdom-quotes.ts'
import { dedupeQuotes } from '../scripts/import-sidebar-quotes/utils.ts'

describe('normalizeMindgrowthQuotesZhFromFile', () => {
  it('parses curated mindgrowth JSONL with categories', () => {
    const quotes = normalizeMindgrowthQuotesZhFromFile()
    expect(quotes.length).toBeGreaterThanOrEqual(250)
    for (const quote of quotes.slice(0, 20)) {
      expect(quote.source).toBe('mindgrowth-zh')
      expect(quote.text.length).toBeGreaterThan(0)
      expect([...quote.text].length).toBeLessThanOrEqual(40)
      expect(quote.category).toBeTruthy()
    }
    expect(quotes.some((quote) => quote.category === 'thinking')).toBe(true)
    expect(quotes.some((quote) => quote.category === 'growth')).toBe(true)
  })
})

describe('normalizeWisdomQuotesZhFromFile', () => {
  it('parses JSONL rows into zh quotes with length filter', () => {
    const quotes = normalizeWisdomQuotesZhFromFile()
    expect(quotes.length).toBeGreaterThan(1000)
    for (const quote of quotes.slice(0, 20)) {
      expect(quote.source).toBe('wisdom-quotes-zh')
      expect(quote.text.length).toBeGreaterThan(0)
      expect([...quote.text].length).toBeLessThanOrEqual(40)
      expect(quote.author).not.toMatch(/张雪峰/)
    }
  })
})

describe('normalizeWisdomQuotesEnFromFile', () => {
  it('parses english array with length filter', () => {
    const quotes = normalizeWisdomQuotesEnFromFile()
    expect(quotes.length).toBeGreaterThan(500)
    for (const quote of quotes.slice(0, 20)) {
      expect(quote.source).toBe('wisdom-quotes-en')
      expect([...quote.text].length).toBeLessThanOrEqual(120)
    }
  })
})

describe('normalizeEchoesFromExtracted', () => {
  it('loads paired zh/en rows from frozen extracted JSON', () => {
    const { zh, en } = normalizeEchoesFromExtracted()
    expect(zh.length).toBeGreaterThan(100)
    expect(en.length).toBeGreaterThan(100)
    expect(
      zh.some((quote) => quote.source === 'echoes-zh' && quote.category === 'philosophers')
    ).toBe(true)
    expect(
      en.some((quote) => quote.source === 'echoes-en' && quote.category === 'philosophers')
    ).toBe(true)
  })
})

describe('runImport', () => {
  it('writes validated quote pools above minimum thresholds', () => {
    const { zhCount, enCount } = runImport()
    expect(zhCount).toBeGreaterThanOrEqual(8000)
    expect(enCount).toBeGreaterThanOrEqual(1000)
  })
})

describe('dedupeQuotes', () => {
  it('removes duplicate text within a locale bucket', () => {
    const merged = dedupeQuotes(
      [
        {
          id: 'a:1',
          text: 'Hello',
          author: 'A',
          source: 'wisdom-quotes-en',
        },
        {
          id: 'a:2',
          text: 'hello',
          author: 'B',
          source: 'wisdom-quotes-en',
        },
      ],
      'en'
    )
    expect(merged).toHaveLength(1)
  })
})
