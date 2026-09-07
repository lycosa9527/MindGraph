import { describe, expect, it } from 'vitest'

import { inferFoundOldest } from '@/utils/workshopMessagePage'

describe('inferFoundOldest', () => {
  it('treats a short initial page as the start of the thread', () => {
    expect(inferFoundOldest(2, 50, 0)).toBe(true)
    expect(inferFoundOldest(0, 50, 0)).toBe(true)
  })

  it('keeps paging when the older window is full', () => {
    expect(inferFoundOldest(50, 50, 0)).toBe(false)
  })

  it('does not guess when the fetch is anchored around a focus id', () => {
    expect(inferFoundOldest(2, 45, 25)).toBe(false)
  })
})
