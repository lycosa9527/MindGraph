import { describe, expect, it } from 'vitest'

import { isCollabGuestAiBlocked } from '@/composables/collab/useCollabGuestAiGate'

describe('isCollabGuestAiBlocked', () => {
  it('allows AI when collab is off', () => {
    expect(isCollabGuestAiBlocked(false, false)).toBe(false)
    expect(isCollabGuestAiBlocked(false, true)).toBe(false)
  })

  it('allows the diagram owner during collab', () => {
    expect(isCollabGuestAiBlocked(true, true)).toBe(false)
  })

  it('blocks guests during collab', () => {
    expect(isCollabGuestAiBlocked(true, false)).toBe(true)
  })
})
