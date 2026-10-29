import { describe, expect, it } from 'vitest'

import {
  isStandaloneMindmateSeminarPath,
  shouldAutoSaveSeminarOnOwnerEnd,
  shouldRefreshSavedSeminarLibrary,
  withoutSavedSeminarQuery,
} from '@/utils/mindmateSeminarLibrarySave'

describe('shouldAutoSaveSeminarOnOwnerEnd', () => {
  it('saves when the owner ends the seminar', () => {
    expect(shouldAutoSaveSeminarOnOwnerEnd('host', true)).toBe(true)
  })

  it('does not save for a guest, an idle close, or someone who only left', () => {
    expect(shouldAutoSaveSeminarOnOwnerEnd('host', false)).toBe(false)
    expect(shouldAutoSaveSeminarOnOwnerEnd('expired', true)).toBe(false)
    expect(shouldAutoSaveSeminarOnOwnerEnd('left', true)).toBe(false)
  })
})

describe('shouldRefreshSavedSeminarLibrary', () => {
  it('refreshes after the host ends the room or it goes idle', () => {
    expect(shouldRefreshSavedSeminarLibrary('host')).toBe(true)
    expect(shouldRefreshSavedSeminarLibrary('expired')).toBe(true)
  })

  it('does not refresh when someone only leaves a live room', () => {
    expect(shouldRefreshSavedSeminarLibrary('left')).toBe(false)
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

describe('isStandaloneMindmateSeminarPath', () => {
  it('matches the dedicated seminar page only', () => {
    expect(isStandaloneMindmateSeminarPath('/mindmate/seminar')).toBe(true)
    expect(isStandaloneMindmateSeminarPath('/mindmate/seminar/extra')).toBe(true)
    expect(isStandaloneMindmateSeminarPath('/mindmate')).toBe(false)
    expect(isStandaloneMindmateSeminarPath('/canvas')).toBe(false)
  })
})
