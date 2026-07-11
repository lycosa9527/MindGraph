import { afterEach, describe, expect, it, vi } from 'vitest'

import { safeRandomUUID } from '@/utils/safeRandomUUID'

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

describe('safeRandomUUID', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('uses crypto.randomUUID when available', () => {
    const expected = '11111111-2222-4333-8444-555555555555'
    vi.stubGlobal('crypto', {
      randomUUID: () => expected,
      getRandomValues: (arr: Uint8Array) => arr,
    })
    expect(safeRandomUUID()).toBe(expected)
  })

  it('falls back to getRandomValues when randomUUID is missing', () => {
    vi.stubGlobal('crypto', {
      getRandomValues: (arr: Uint8Array) => {
        for (let i = 0; i < arr.length; i += 1) {
          arr[i] = i
        }
        return arr
      },
    })
    expect(safeRandomUUID()).toMatch(UUID_RE)
  })

  it('falls back when crypto is unavailable', () => {
    vi.stubGlobal('crypto', undefined)
    const id = safeRandomUUID()
    expect(id.length).toBeGreaterThan(8)
    expect(id).toContain('-')
  })
})
