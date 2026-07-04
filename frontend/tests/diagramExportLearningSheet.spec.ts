import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import {
  isLearningSheetRasterCapture,
  learningSheetIncludeAnswers,
  runLearningSheetRasterCapture,
} from '@/utils/diagramExportLearningSheet'
import { LEARNING_SHEET_BLANK_TEXT } from '@/stores/specLoader/utils'

describe('diagramExportLearningSheet', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({
      matches: false,
      media: '',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })))
    setActivePinia(createPinia())
  })

  it('detects learning sheet capture only when blanks exist', () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('mindmap')
    expect(isLearningSheetRasterCapture(store)).toBe(false)

    store.setLearningSheetMode(true)
    const branch = store.data?.nodes.find((node) => node.id.startsWith('branch-'))
    if (!branch) throw new Error('missing branch')
    store.emptyNodeForLearningSheet(branch.id)
    expect(isLearningSheetRasterCapture(store)).toBe(true)
  })

  it('honors answerMode include flag', () => {
    expect(learningSheetIncludeAnswers({ colorMode: 'color', layout: 'landscape', answerMode: 'include' })).toBe(true)
    expect(learningSheetIncludeAnswers({ colorMode: 'color', layout: 'landscape', answerMode: 'exclude' })).toBe(false)
  })

  it('hides answers during exclude capture', async () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('mindmap')
    store.setLearningSheetMode(true)
    const branch = store.data?.nodes.find((node) => node.id.startsWith('branch-'))
    if (!branch) throw new Error('missing branch')
    store.emptyNodeForLearningSheet(branch.id)

    await runLearningSheetRasterCapture(
      store,
      { colorMode: 'color', layout: 'landscape', answerMode: 'exclude' },
      () => {
        expect(store.learningSheetShowAnswers).toBe(false)
        return 'ok'
      }
    )

    const blanked = store.data?.nodes.find((node) => node.id === branch.id)
    expect(blanked?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
  })
})
