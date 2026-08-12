import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it } from 'vitest'

import { buildAiContentLevelInstructions } from '@/config/aiContentLevels'
import { useAiContentLevelStore } from '@/stores/aiContentLevel'

describe('AI content level generation instructions', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    setActivePinia(createPinia())
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
})
