import { beforeEach, describe, expect, it } from 'vitest'

import {
  clearQuoteSessionCache,
  detectSidebarQuoteUserLogin,
  pickRandomQuoteExcluding,
  preferQuotesWithAuthor,
  quoteLocaleBucket,
  readQuoteSessionCache,
  remainingQuoteRotateMs,
  rememberSidebarQuoteUser,
  resetSidebarQuoteSessionState,
  resolveSidebarQuote,
  writeQuoteSessionCache,
  writeQuoteSessionForPick,
} from '@/composables/sidebar/sidebarQuotePicker'
import {
  SIDEBAR_QUOTE_ROTATE_MS,
  formatSidebarQuoteTextAuthor,
  isChineseUiLocale,
} from '@/types/sidebar-quotes'
import type { SidebarQuote } from '@/types/sidebar-quotes'

const sampleQuotes: SidebarQuote[] = [
  {
    id: 'wisdom-quotes-en:aaa',
    text: 'Know thyself.',
    author: 'Socrates',
    source: 'wisdom-quotes-en',
  },
  {
    id: 'wisdom-quotes-en:bbb',
    text: 'To be, or not to be.',
    author: 'Shakespeare',
    source: 'wisdom-quotes-en',
  },
]

describe('quoteLocaleBucket', () => {
  it('routes zh and zh-tw to Chinese quotes', () => {
    expect(isChineseUiLocale('zh')).toBe(true)
    expect(isChineseUiLocale('zh-tw')).toBe(true)
    expect(quoteLocaleBucket('zh')).toBe('zh')
    expect(quoteLocaleBucket('zh-tw')).toBe('zh')
  })

  it('routes all other UI languages to English quotes', () => {
    expect(quoteLocaleBucket('en')).toBe('en')
    expect(quoteLocaleBucket('fr')).toBe('en')
    expect(quoteLocaleBucket('ja')).toBe('en')
  })
})

describe('preferQuotesWithAuthor', () => {
  it('prefers rows with author when available', () => {
    const pool = preferQuotesWithAuthor([
      ...sampleQuotes,
      { id: 'x', text: 'No author quote', author: '', source: 'wisdom-quotes-en' },
    ])
    expect(pool.every((row) => row.author.trim().length > 0)).toBe(true)
  })

  it('falls back to the full pool when no authors exist', () => {
    const pool = preferQuotesWithAuthor([
      { id: 'x', text: 'No author quote', author: '', source: 'wisdom-quotes-en' },
    ])
    expect(pool).toHaveLength(1)
  })
})

describe('formatSidebarQuoteTextAuthor', () => {
  it('joins quote text and author with an em dash', () => {
    expect(formatSidebarQuoteTextAuthor('Hello', 'World')).toBe('Hello — World')
    expect(formatSidebarQuoteTextAuthor('Hello', '')).toBe('Hello')
  })
})

describe('remainingQuoteRotateMs', () => {
  it('returns full interval when shownAt is missing', () => {
    expect(remainingQuoteRotateMs(undefined)).toBe(SIDEBAR_QUOTE_ROTATE_MS)
  })

  it('returns remaining time until rotation', () => {
    const now = 1_000_000
    const shownAt = now - 2 * 60 * 1000
    expect(remainingQuoteRotateMs(shownAt, now)).toBe(3 * 60 * 1000)
  })

  it('returns zero when the interval has elapsed', () => {
    const now = 1_000_000
    const shownAt = now - SIDEBAR_QUOTE_ROTATE_MS - 1
    expect(remainingQuoteRotateMs(shownAt, now)).toBe(0)
  })
})

describe('writeQuoteSessionForPick', () => {
  beforeEach(() => {
    resetSidebarQuoteSessionState()
    clearQuoteSessionCache()
  })

  it('preserves shownAt when reusing the same cached quote', () => {
    const quote = sampleQuotes[0]
    writeQuoteSessionForPick(quote, { forceNew: true, now: 1000 })
    writeQuoteSessionForPick(quote, { forceNew: false, now: 5000 })
    expect(readQuoteSessionCache()).toEqual({ id: quote.id, shownAt: 1000 })
  })

  it('resets shownAt on a forced new quote', () => {
    const quote = sampleQuotes[0]
    writeQuoteSessionForPick(quote, { forceNew: true, now: 1000 })
    writeQuoteSessionForPick(sampleQuotes[1], { forceNew: true, now: 9000 })
    expect(readQuoteSessionCache()?.shownAt).toBe(9000)
  })
})

describe('pickRandomQuoteExcluding', () => {
  beforeEach(() => {
    resetSidebarQuoteSessionState()
  })

  it('avoids the excluded quote when another option exists', () => {
    const picked = pickRandomQuoteExcluding(sampleQuotes, 'wisdom-quotes-en:aaa', () => 0)
    expect(picked?.id).toBe('wisdom-quotes-en:bbb')
  })

  it('falls back to the only quote when exclusion would empty the pool', () => {
    const picked = pickRandomQuoteExcluding(
      sampleQuotes.slice(0, 1),
      'wisdom-quotes-en:aaa',
      () => 0
    )
    expect(picked?.id).toBe('wisdom-quotes-en:aaa')
  })
})

describe('sidebar quote rotation policy', () => {
  it('rotates on a five-minute cadence constant', () => {
    expect(SIDEBAR_QUOTE_ROTATE_MS).toBe(5 * 60 * 1000)
  })
})

describe('resolveSidebarQuote', () => {
  beforeEach(() => {
    resetSidebarQuoteSessionState()
    clearQuoteSessionCache()
  })

  it('picks a quote when no cache exists', () => {
    const picked = resolveSidebarQuote(sampleQuotes, null, () => 0)
    expect(picked?.id).toBe('wisdom-quotes-en:aaa')
  })

  it('reuses session cache after the page session is hydrated', () => {
    writeQuoteSessionCache({ id: 'wisdom-quotes-en:bbb' })
    resolveSidebarQuote(sampleQuotes, 'wisdom-quotes-en:aaa', () => 0)
    const cached = resolveSidebarQuote(sampleQuotes, readQuoteSessionCache()?.id ?? null, () => 0)
    expect(cached?.id).toBe('wisdom-quotes-en:bbb')
  })

  it('ignores session cache on a fresh page load before hydration', () => {
    writeQuoteSessionCache({ id: 'wisdom-quotes-en:bbb' })
    const picked = resolveSidebarQuote(sampleQuotes, 'wisdom-quotes-en:bbb', () => 0)
    expect(picked?.id).toBe('wisdom-quotes-en:aaa')
  })
})

describe('login rotation helpers', () => {
  beforeEach(() => {
    resetSidebarQuoteSessionState()
    clearQuoteSessionCache()
  })

  it('detects login when the active user changes', () => {
    rememberSidebarQuoteUser('10')
    expect(detectSidebarQuoteUserLogin('10')).toBe(false)
    expect(detectSidebarQuoteUserLogin('11')).toBe(true)
  })

  it('treats the first authenticated user as a login', () => {
    expect(detectSidebarQuoteUserLogin('42')).toBe(true)
  })
})
