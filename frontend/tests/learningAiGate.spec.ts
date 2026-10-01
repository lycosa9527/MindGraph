import { effectScope } from 'vue'

import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useLearningAiGate } from '@/composables/learningSpace/useLearningAiGate'
import { useAuthStore } from '@/stores/auth'
import { useLearningAssignmentCanvasStore } from '@/stores/learningAssignmentCanvas'

describe('useLearningAiGate', () => {
  beforeEach(() => {
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

  it('denies all AI for students outside homework canvas', () => {
    const authStore = useAuthStore()
    authStore.user = { id: '1', username: 'stu', role: 'student' }

    const scope = effectScope()
    const gate = scope.run(() => useLearningAiGate())
    if (!gate) {
      throw new Error('expected gate')
    }

    expect(gate.studentManualEditOnly.value).toBe(true)
    expect(gate.showCanvasAiFeatures.value).toBe(false)
    expect(gate.can('topic_generate')).toBe(false)
    expect(gate.requireCapability('conversational_edit')).toBe(false)
    scope.stop()
  })

  it('shows AI on homework when teacher enabled ai_assist and granular flags', () => {
    const authStore = useAuthStore()
    authStore.user = { id: '2', username: 'stu2', role: 'student' }

    const ls = useLearningAssignmentCanvasStore()
    ls.assignmentId = 42
    ls.permissions = {
      ai_assist: true,
      topic_generate: true,
      file_generate: false,
      web_generate: false,
      voice_summary: false,
      ai_brainstorm: false,
      conversational_edit: true,
      node_subgraph: false,
      node_explain: false,
      mind_classroom: false,
      translate: false,
    }

    const scope = effectScope()
    const gate = scope.run(() => useLearningAiGate())
    if (!gate) {
      throw new Error('expected gate')
    }

    expect(gate.studentManualEditOnly.value).toBe(false)
    expect(gate.showCanvasAiFeatures.value).toBe(true)
    expect(gate.can('topic_generate')).toBe(true)
    expect(gate.can('file_generate')).toBe(false)
    scope.stop()
  })

  it('keeps AI enabled for teachers on library canvas', () => {
    const authStore = useAuthStore()
    authStore.user = { id: '3', username: 't', role: 'teacher' }

    const scope = effectScope()
    const gate = scope.run(() => useLearningAiGate())
    if (!gate) {
      throw new Error('expected gate')
    }

    expect(gate.showCanvasAiFeatures.value).toBe(true)
    expect(gate.can('topic_generate')).toBe(true)
    scope.stop()
  })
})
