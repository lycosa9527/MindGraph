import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { buildAiContentLevelInstructions } from '@/config/aiContentLevels'
import { useAiContentLevelStore } from '@/stores/aiContentLevel'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/composables/core/notifications', () => ({
  notify: { error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

describe('AI content level generation instructions', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
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
    vi.unstubAllGlobals()
  })

  it('does not constrain general content', () => {
    expect(buildAiContentLevelInstructions('general', 'en')).toBeUndefined()
  })

  it('builds prompt-language instructions for learner levels', () => {
    expect(buildAiContentLevelInstructions('primary', 'en')).toContain('primary school')
    expect(buildAiContentLevelInstructions('senior', 'zh-CN')).toContain('高中')
  })

  it('uses professional guidance for expert audiences', () => {
    expect(buildAiContentLevelInstructions('expert', 'en')).toContain('expert / professional')
    expect(buildAiContentLevelInstructions('expert', 'zh')).toContain('专家/专业人士')
  })

  it('tracks unsaved canvases independently and migrates levels after save', () => {
    const store = useAiContentLevelStore()
    const firstUnsavedKey = store.diagramKey(null)
    store.markDiagramGenerated(firstUnsavedKey, 'senior')
    store.migrateGeneratedLevel(firstUnsavedKey, 'diagram-1')

    expect(store.getGeneratedLevel(firstUnsavedKey)).toBeNull()
    expect(store.getGeneratedLevel(store.diagramKey('diagram-1'))).toBe('senior')

    store.resetGeneratedLevelSession()
    expect(store.diagramKey(null)).not.toBe(firstUnsavedKey)
  })

  it('hydrates a saved server 专业程度 and treats it as user-set', () => {
    const store = useAiContentLevelStore()
    store.hydrateFromProfile('expert')
    expect(store.level).toBe('expert')
    expect(store.userSet).toBe(true)
  })

  it('resets to general when the profile has no saved 专业程度', () => {
    const store = useAiContentLevelStore()
    store.hydrateFromProfile('expert')
    store.hydrateFromProfile(null)
    expect(store.level).toBe('general')
    expect(store.userSet).toBe(false)
  })

  it('persists the picked level for a signed-in user', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ai_content_level: 'university' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const authStore = useAuthStore()
    authStore.user = {
      id: '1',
      username: 'teacher',
      role: 'teacher',
    }
    const store = useAiContentLevelStore()
    const saved = await store.setLevel('university')
    expect(saved).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/diagram-preferences',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ ai_content_level: 'university' }),
      })
    )
    expect(authStore.user?.aiContentLevel).toBe('university')
    expect(store.level).toBe('university')
  })
})
