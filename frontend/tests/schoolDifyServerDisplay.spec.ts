import { describe, expect, it } from 'vitest'

import {
  applySchoolDifyUrlInput,
  schoolDifyCredentialDraftUrl,
  schoolDifyDisplayedKey,
  schoolDifyPairWrite,
  schoolDifyShownUrl,
  schoolDifyUsingGlobalUrl,
} from '@/utils/schoolDifyServerDisplay'

const GLOBAL_URL = 'http://dify.mindspringedu.com/v1'
const SCHOOL_URL = 'https://school.example/v1'

describe('school Dify server display', () => {
  it('shows the global URL and masked key when the school slot is blank', () => {
    expect(schoolDifyShownUrl(false, '', '', GLOBAL_URL)).toBe(GLOBAL_URL)
    expect(schoolDifyUsingGlobalUrl(false, '', '', GLOBAL_URL)).toBe(true)
    expect(schoolDifyDisplayedKey(null, 'app-••••••••••••ZGKv')).toBe('app-••••••••••••ZGKv')
    expect(schoolDifyCredentialDraftUrl('', '', GLOBAL_URL)).toBe('')
  })

  it('keeps a school URL and school key ahead of the global default', () => {
    expect(schoolDifyShownUrl(false, SCHOOL_URL, SCHOOL_URL, GLOBAL_URL)).toBe(SCHOOL_URL)
    expect(schoolDifyUsingGlobalUrl(false, SCHOOL_URL, SCHOOL_URL, GLOBAL_URL)).toBe(false)
    expect(schoolDifyDisplayedKey('app-••••••••••••qFQX', 'app-••••••••••••ZGKv')).toBe(
      'app-••••••••••••qFQX'
    )
  })

  it('treats an edit back to the global URL as clearing a school override', () => {
    expect(applySchoolDifyUrlInput(GLOBAL_URL, SCHOOL_URL, GLOBAL_URL)).toEqual({
      urlDirty: true,
      draftUrl: '',
    })
    expect(schoolDifyShownUrl(true, '', SCHOOL_URL, GLOBAL_URL)).toBe(GLOBAL_URL)
    expect(schoolDifyCredentialDraftUrl('', '', GLOBAL_URL)).toBe('')
  })

  it('pairs a newly typed key with the URL currently shown', () => {
    expect(schoolDifyCredentialDraftUrl('', 'app-new-key', GLOBAL_URL)).toBe(GLOBAL_URL)
  })

  it('snaps a cleared blank slot back to the global URL', () => {
    expect(applySchoolDifyUrlInput('', '', GLOBAL_URL)).toEqual({
      urlDirty: false,
      draftUrl: '',
    })
    expect(schoolDifyShownUrl(false, '', '', GLOBAL_URL)).toBe(GLOBAL_URL)
  })

  it('clears the stored pair when a school URL is returned to the global default', () => {
    expect(
      schoolDifyPairWrite({
        draftUrl: '',
        typedKey: '',
        shownUrl: GLOBAL_URL,
        urlDirty: true,
        schoolUrl: SCHOOL_URL,
        hasSchoolKey: true,
      })
    ).toEqual({ clear: true, url: null, key: null })
  })

  it('leaves a stored key untouched when the slot is already on the global URL', () => {
    expect(
      schoolDifyPairWrite({
        draftUrl: '',
        typedKey: '',
        shownUrl: GLOBAL_URL,
        urlDirty: false,
        schoolUrl: '',
        hasSchoolKey: true,
      })
    ).toBeNull()
  })

  it('stores a new key together with the URL on screen', () => {
    expect(
      schoolDifyPairWrite({
        draftUrl: '',
        typedKey: 'app-new-key',
        shownUrl: GLOBAL_URL,
        urlDirty: false,
        schoolUrl: '',
        hasSchoolKey: false,
      })
    ).toEqual({ clear: false, url: GLOBAL_URL, key: 'app-new-key' })
  })
})
