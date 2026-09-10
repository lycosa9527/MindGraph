import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { discardCanvasTranslatePreview } from '@/composables/canvasPage/discardCanvasTranslatePreview'
import { useDiagramStore } from '@/stores/diagram'
import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'

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

describe('discardCanvasTranslatePreview', () => {
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

  it('restores the original spec and drops the temp translate snapshot', () => {
    const diagramStore = useDiagramStore()
    const translateUi = useDiagramTranslateUiStore()
    const original = {
      topic: '光合作用',
      children: [{ id: 'a', text: '叶绿体' }],
    }
    diagramStore.loadFromSpec(
      { topic: 'Photosynthesis', children: [{ id: 'a', text: 'Chloroplast' }] },
      'mindmap'
    )
    translateUi.armPending('en', original)
    translateUi.setTranslatedSpec({
      topic: 'Photosynthesis',
      children: [{ id: 'a', text: 'Chloroplast' }],
    })
    translateUi.setViewingTranslated(true)

    discardCanvasTranslatePreview()

    expect(translateUi.hasPendingTranslate).toBe(false)
    expect(translateUi.translatedSpec).toBeNull()
    expect(translateUi.pendingSourceSpec).toBeNull()
    expect(translateUi.viewingTranslated).toBe(false)
    const texts = (diagramStore.data?.nodes ?? []).map((node) => node.text)
    expect(texts).toContain('光合作用')
    expect(texts).not.toContain('Photosynthesis')
  })
})
