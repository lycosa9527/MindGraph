import { afterEach, describe, expect, it } from 'vitest'

import {
  clearSavedLoginCredentials,
  loadSavedLoginIdentifier,
  saveLoginIdentifier,
} from '@/utils/savedLoginCredentials'

describe('savedLoginCredentials', () => {
  afterEach(() => {
    clearSavedLoginCredentials()
  })

  it('saves and loads identifier only', () => {
    saveLoginIdentifier('13800138000')
    expect(loadSavedLoginIdentifier()).toBe('13800138000')
  })

  it('trims identifier on save', () => {
    saveLoginIdentifier('  teacher@school.edu  ')
    expect(loadSavedLoginIdentifier()).toBe('teacher@school.edu')
  })

  it('ignores empty saves', () => {
    saveLoginIdentifier('')
    expect(loadSavedLoginIdentifier()).toBeNull()
  })

  it('clears stored identifier', () => {
    saveLoginIdentifier('13800138000')
    clearSavedLoginCredentials()
    expect(loadSavedLoginIdentifier()).toBeNull()
  })

  it('migrates legacy payload with password field to identifier only', () => {
    localStorage.setItem(
      'mg_saved_login_v1',
      JSON.stringify({ identifier: '13800138000', password: 'secret' })
    )
    expect(loadSavedLoginIdentifier()).toBe('13800138000')
  })
})
