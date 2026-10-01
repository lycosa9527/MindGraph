import { describe, expect, it } from 'vitest'

import {
  isStandaloneMindmateCollabPath,
  shouldAutoSaveSeminarOnOwnerEnd,
  withoutSavedSeminarQuery,
} from '@/utils/mindmateCollabLibrarySave'

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

describe('withoutSavedSeminarQuery', () => {
  it('removes saved_seminar and keeps other query params', () => {
    expect(withoutSavedSeminarQuery({ saved_seminar: 'room-1', tab: 'chat' })).toEqual({
      tab: 'chat',
    })
  })

  it('returns null when no saved seminar is open', () => {
    expect(withoutSavedSeminarQuery({ tab: 'chat' })).toBeNull()
    expect(withoutSavedSeminarQuery({})).toBeNull()
  })
})

describe('isStandaloneMindmateCollabPath', () => {
  it('matches the dedicated seminar page only', () => {
    expect(isStandaloneMindmateCollabPath('/mindmate/collab')).toBe(true)
    expect(isStandaloneMindmateCollabPath('/mindmate/collab/extra')).toBe(true)
    expect(isStandaloneMindmateCollabPath('/mindmate')).toBe(false)
    expect(isStandaloneMindmateCollabPath('/canvas')).toBe(false)
  })
})
