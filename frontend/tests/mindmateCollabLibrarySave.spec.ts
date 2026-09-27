import { describe, expect, it } from 'vitest'

import { shouldAutoSaveSeminarOnOwnerEnd } from '@/utils/mindmateCollabLibrarySave'

describe('shouldAutoSaveSeminarOnOwnerEnd', () => {
  it('saves when the owner ends the seminar', () => {
    expect(shouldAutoSaveSeminarOnOwnerEnd('host', true)).toBe(true)
  })

  it('does not save for a guest, an idle close, or someone who only left', () => {
    expect(shouldAutoSaveSeminarOnOwnerEnd('host', false)).toBe(false)
    expect(shouldAutoSaveSeminarOnOwnerEnd('idle', true)).toBe(false)
    expect(shouldAutoSaveSeminarOnOwnerEnd('left', true)).toBe(false)
  })
})
