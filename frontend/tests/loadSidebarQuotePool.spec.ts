import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  loadSidebarQuotePool,
  resetSidebarQuotePoolCache,
} from '@/composables/sidebar/sidebarQuotePicker'
import type { SidebarQuote } from '@/types/sidebar-quotes'

vi.mock('@/assets/sidebar-quotes-zh.json?url', () => ({
  default: '/assets/sidebar-quotes-zh.json',
}))

vi.mock('@/assets/sidebar-quotes-en.json?url', () => ({
  default: '/assets/sidebar-quotes-en.json',
}))

const sampleEnQuotes: SidebarQuote[] = [
  {
    id: 'wisdom-quotes-en:aaa',
    text: 'Know thyself.',
    author: 'Socrates',
    source: 'wisdom-quotes-en',
  },
]

const sampleZhQuotes: SidebarQuote[] = [
  {
    id: 'wisdom-quotes-zh:bbb',
    text: '知人者智，自知者明。',
    author: '老子',
    source: 'wisdom-quotes-zh',
  },
]

function mockFetchResponse(rows: SidebarQuote[]): Response {
  return {
    ok: true,
    json: async () => rows,
  } as Response
}

describe('loadSidebarQuotePool', () => {
  beforeEach(() => {
    resetSidebarQuotePoolCache()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetches the English pool on demand', async () => {
    vi.mocked(fetch).mockResolvedValue(mockFetchResponse(sampleEnQuotes))

    const pool = await loadSidebarQuotePool('en')

    expect(pool).toEqual(sampleEnQuotes)
    expect(fetch).toHaveBeenCalledWith('/assets/sidebar-quotes-en.json')
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('fetches the Chinese pool on demand', async () => {
    vi.mocked(fetch).mockResolvedValue(mockFetchResponse(sampleZhQuotes))

    const pool = await loadSidebarQuotePool('zh')

    expect(pool).toEqual(sampleZhQuotes)
    expect(fetch).toHaveBeenCalledWith('/assets/sidebar-quotes-zh.json')
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('reuses the in-memory cache for the same locale bucket', async () => {
    vi.mocked(fetch).mockResolvedValue(mockFetchResponse(sampleEnQuotes))

    await loadSidebarQuotePool('en')
    await loadSidebarQuotePool('en')

    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('throws when fetch fails', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 404,
    } as Response)

    await expect(loadSidebarQuotePool('en')).rejects.toThrow('Failed to load sidebar quotes (404)')
  })
})
