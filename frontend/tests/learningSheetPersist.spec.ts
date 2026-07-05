import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  handleLearningSheetPickNodeClick,
  learningSheetFloatBarOpen,
  learningSheetPickActive,
  restoreLearningSheetUiFromDiagram,
  toggleLearningSheetAnswersVisibility,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import { LEARNING_SHEET_BLANK_TEXT } from '@/stores/specLoader/utils'
import { useDiagramStore } from '@/stores/diagram'

describe('learning sheet persistence', () => {
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
    learningSheetPickActive.value = false
    learningSheetFloatBarOpen.value = false
  })

  function loadMindMapWithBranch(): { branchId: string; branchText: string } {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('mindmap')

    const branch = diagramStore.data?.nodes.find(
      (node) => node.id.startsWith('branch-') && String(node.text ?? '').trim().length > 0
    )
    if (!branch) {
      throw new Error('expected a branch node in default mind map template')
    }

    return { branchId: branch.id, branchText: String(branch.text ?? '').trim() }
  }

  it('round-trips learning sheet blanks and show-answers preference via spec save/load', () => {
    const diagramStore = useDiagramStore()
    const { branchId, branchText } = loadMindMapWithBranch()

    diagramStore.setLearningSheetMode(true)
    learningSheetPickActive.value = true
    handleLearningSheetPickNodeClick(branchId)
    diagramStore.setLearningSheetShowAnswers(false)

    const spec = diagramStore.getSpecForSave()
    expect(spec).toBeTruthy()
    expect(spec!.is_learning_sheet).toBe(true)
    expect(spec!.learning_sheet_show_answers).toBe(false)

    const blankedNode = (spec!.nodes as { id: string; text?: string; data?: Record<string, unknown> }[]).find(
      (node) => node.id === branchId
    )
    expect(blankedNode?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
    expect(blankedNode?.data?.hiddenAnswer).toBe(branchText)

    diagramStore.loadFromSpec(spec!, diagramStore.type!)

    expect(diagramStore.isLearningSheet).toBe(true)
    expect(diagramStore.learningSheetShowAnswers).toBe(false)
    expect(diagramStore.isNodeBlankedForLearningSheet(branchId)).toBe(true)

    const reloaded = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect(reloaded?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
    expect((reloaded?.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer).toBe(branchText)
  })

  it('restores float bar UI when diagram reloads in learning sheet mode', () => {
    const diagramStore = useDiagramStore()
    loadMindMapWithBranch()
    diagramStore.setLearningSheetMode(true)

    learningSheetFloatBarOpen.value = false
    restoreLearningSheetUiFromDiagram()

    expect(learningSheetFloatBarOpen.value).toBe(true)
    expect(learningSheetPickActive.value).toBe(false)
  })

  it('toggles show-answers preference', () => {
    const diagramStore = useDiagramStore()
    loadMindMapWithBranch()
    diagramStore.setLearningSheetMode(true)
    expect(diagramStore.learningSheetShowAnswers).toBe(true)

    expect(toggleLearningSheetAnswersVisibility()).toBe(true)
    expect(diagramStore.learningSheetShowAnswers).toBe(false)

    expect(toggleLearningSheetAnswersVisibility()).toBe(true)
    expect(diagramStore.learningSheetShowAnswers).toBe(true)

    diagramStore.setLearningSheetMode(false)
    expect(toggleLearningSheetAnswersVisibility()).toBe(false)
  })
})
