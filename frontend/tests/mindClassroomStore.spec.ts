import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useMindClassroomStore } from '@/stores/mindClassroom'

describe('mind classroom slide lecture gate', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('keeps a saved slide lecture choice off the store while the feature is off', () => {
    localStorage.setItem('mg-mind-classroom-presentation', 'slide_deck')
    const store = useMindClassroomStore()
    expect(store.presentation).toBe('canvas_tour')
    expect(localStorage.getItem('mg-mind-classroom-presentation')).toBe('canvas_tour')
  })

  it('rejects selecting or starting slide lecture while the feature is off', () => {
    const store = useMindClassroomStore()
    store.setPresentation('slide_deck')
    expect(store.presentation).toBe('canvas_tour')
    store.beginSession([], 'slide_deck')
    expect(store.activeMode).toBe('canvas_tour')
  })
})
