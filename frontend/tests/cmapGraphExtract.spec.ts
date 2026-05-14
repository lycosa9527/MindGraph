import { describe, expect, it } from 'vitest'

import { extractConceptGraphFromHandles } from '@/utils/cmapGraphExtract'

describe('extractConceptGraphFromHandles', () => {
  it('returns null for empty streams', () => {
    expect(extractConceptGraphFromHandles([])).toBe(null)
  })
})
