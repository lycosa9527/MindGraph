import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/composables/core/notifications', () => ({
  notify: { warning: vi.fn(), error: vi.fn(), success: vi.fn(), info: vi.fn() },
}))

import {
  useDiagramSpecForPersist,
  useDiagramSpecForSave,
} from '@/composables/editor/useDiagramSpecForSave'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'

function memoryStorage(): Storage {
  const map = new Map<string, string>()
  return {
    get length() {
      return map.size
    },
    clear: () => map.clear(),
    getItem: (key: string) => map.get(key) ?? null,
    key: (index: number) => [...map.keys()][index] ?? null,
    removeItem: (key: string) => {
      map.delete(key)
    },
    setItem: (key: string, value: string) => {
      map.set(key, value)
    },
  }
}

describe('diagram spec for save vs persist', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', memoryStorage())
    vi.stubGlobal('sessionStorage', memoryStorage())
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
  })

  it('keeps useDiagramSpecForSave pure so template reads cannot freeze the UI', () => {
    const diagramStore = useDiagramStore()
    const llmResultsStore = useLLMResultsStore()

    diagramStore.loadFromSpec(
      {
        topic: 'freeze-regression',
        children: [{ id: 'a', text: 'A', children: [{ id: 'a1', text: 'A1' }] }],
      },
      'mindmap'
    )

    llmResultsStore.expectedDiagramType = 'mindmap'
    llmResultsStore.selectedModel = 'deepseek'
    llmResultsStore.results = {
      deepseek: {
        success: true,
        spec: { topic: 'freeze-regression', children: [] },
        diagramType: 'mindmap',
        elapsed: 1,
        timestamp: 1000,
      },
    }

    const getDiagramSpec = useDiagramSpecForSave()
    getDiagramSpec()
    getDiagramSpec()
    expect(llmResultsStore.results.deepseek?.timestamp).toBe(1000)

    const getDiagramSpecForPersist = useDiagramSpecForPersist()
    getDiagramSpecForPersist()
    expect(llmResultsStore.results.deepseek?.timestamp).toBeGreaterThan(1000)
  })
})
