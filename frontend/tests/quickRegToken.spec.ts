import { afterEach, describe, expect, it } from 'vitest'

import {
  clearStoredQuickRegToken,
  extractQuickRegTokenFromRedirect,
  extractQuickRegTokenFromSearch,
  normalizeQuickRegToken,
  readStoredQuickRegToken,
  writeStoredQuickRegToken,
} from '@/utils/quickRegToken'

const sample = 'abcdefghijklmnopqrstuvwxyz012345'

describe('quickRegToken', () => {
  afterEach(() => {
    clearStoredQuickRegToken()
  })

  it('rejects short or oversized tokens', () => {
    expect(normalizeQuickRegToken('short')).toBe('')
    expect(normalizeQuickRegToken(` ${sample} `)).toBe(sample)
    expect(normalizeQuickRegToken('x'.repeat(513))).toBe('')
  })

  it('reads quick_reg from a query string and from a redirect path', () => {
    expect(extractQuickRegTokenFromSearch(`?quick_reg=${sample}&x=1`)).toBe(sample)
    expect(
      extractQuickRegTokenFromRedirect(`/auth?quick_reg=${sample}`, 'https://example.test')
    ).toBe(sample)
  })

  it('round-trips the token through sessionStorage', () => {
    writeStoredQuickRegToken(sample)
    expect(readStoredQuickRegToken()).toBe(sample)
    clearStoredQuickRegToken()
    expect(readStoredQuickRegToken()).toBe('')
  })
})
