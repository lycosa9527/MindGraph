import { effectScope } from 'vue'

import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useMindMapRibbonState } from '@/canvas-ribbon/useMindMapRibbonState'
import { useAuthStore } from '@/stores/auth'
import { authFetch } from '@/utils/api'

vi.mock('@/utils/api', () => ({
  authFetch: vi.fn(),
}))

describe('useMindMapRibbonState', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    vi.useFakeTimers()
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('does not restore File as the landing tab', () => {
    const authStore = useAuthStore()
    authStore.user = {
      id: '3',
      username: 'teacher',
      role: 'teacher',
      v3RibbonClassic: false,
      v3RibbonTab: 'file',
    }
    const scope = effectScope()
    const state = scope.run(() => useMindMapRibbonState())
    if (!state) {
      throw new Error('expected ribbon state')
    }
    expect(state.activeTab.value).toBe('edit')
    scope.stop()
  })

  it('does not persist File as the last tab', async () => {
    const fetchMock = vi.mocked(authFetch)
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ v3_ribbon_classic: false, v3_ribbon_tab: 'teaching' }),
    } as Response)
    const authStore = useAuthStore()
    authStore.user = {
      id: '4',
      username: 'teacher',
      role: 'teacher',
      v3RibbonClassic: false,
      v3RibbonTab: 'teaching',
    }
    const scope = effectScope()
    const state = scope.run(() => useMindMapRibbonState())
    if (!state) {
      throw new Error('expected ribbon state')
    }
    expect(state.activeTab.value).toBe('teaching')
    state.setActiveTab('file')
    expect(state.activeTab.value).toBe('file')
    await vi.runAllTimersAsync()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(authStore.user?.v3RibbonTab).toBe('teaching')
    scope.stop()
  })

  it('keeps guest height and tab in memory only', () => {
    const scope = effectScope()
    const state = scope.run(() => useMindMapRibbonState())
    if (!state) {
      throw new Error('expected ribbon state')
    }
    expect(state.classic.value).toBe(false)
    expect(state.activeTab.value).toBe('edit')
    state.setActiveTab('teaching')
    state.setClassic(true)
    vi.runAllTimers()
    expect(authFetch).not.toHaveBeenCalled()
    expect(Object.keys(localStorage).filter((key) => key.toLowerCase().includes('ribbon'))).toEqual(
      []
    )
    expect(
      Object.keys(sessionStorage).filter((key) => key.toLowerCase().includes('ribbon'))
    ).toEqual([])
    scope.stop()
  })

  it('patches Postgres after a signed-in tab change and skips ribbon-only storage keys', async () => {
    const fetchMock = vi.mocked(authFetch)
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ v3_ribbon_classic: true, v3_ribbon_tab: 'teaching' }),
    } as Response)
    const authStore = useAuthStore()
    authStore.user = {
      id: '9',
      username: 'teacher',
      role: 'teacher',
      v3RibbonClassic: false,
      v3RibbonTab: 'draw',
    }
    const scope = effectScope()
    const state = scope.run(() => useMindMapRibbonState())
    if (!state) {
      throw new Error('expected ribbon state')
    }
    expect(state.activeTab.value).toBe('edit')
    state.setClassic(true)
    state.setActiveTab('teaching')
    await vi.runAllTimersAsync()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/diagram-preferences',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          v3_ribbon_classic: true,
          v3_ribbon_tab: 'teaching',
        }),
      })
    )
    expect(Object.keys(localStorage).filter((key) => key.toLowerCase().includes('ribbon'))).toEqual(
      []
    )
    expect(
      Object.keys(sessionStorage).filter((key) => key.toLowerCase().includes('ribbon'))
    ).toEqual([])
    scope.stop()
  })
})
