import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { handleLearningSheetPickNodeClick, learningSheetPickActive } from '@/composables/mindMap/useLearningSheetCustomMode'
import { tryCollabGuardedUndo } from '@/composables/canvasPage/useCanvasCollabHistoryGuard'
import { LEARNING_SHEET_BLANK_TEXT } from '@/stores/specLoader/utils'
import { useDiagramStore } from '@/stores/diagram'

describe('learning sheet undo/redo', () => {
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

  function loadMindMapWithBranch(): { branchId: string; branchText: string } {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('mindmap')
    diagramStore.seedHistoryBaselineIfEmpty()

    const branch = diagramStore.data?.nodes.find(
      (node) => node.id.startsWith('branch-') && String(node.text ?? '').trim().length > 0
    )
    if (!branch) {
      throw new Error('expected a branch node in default mind map template')
    }

    return { branchId: branch.id, branchText: String(branch.text ?? '').trim() }
  }

  it('undoes custom pick blank and restore', () => {
    const diagramStore = useDiagramStore()
    const { branchId, branchText } = loadMindMapWithBranch()

    diagramStore.setLearningSheetMode(true)
    learningSheetPickActive.value = true
    handleLearningSheetPickNodeClick(branchId)

    const blanked = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect(blanked?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
    expect(diagramStore.canUndo).toBe(true)

    tryCollabGuardedUndo()

    const restored = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect(restored?.text).toBe(branchText)
  })

  it('undoes random learning sheet blank batch', () => {
    const diagramStore = useDiagramStore()
    loadMindMapWithBranch()

    const spec = diagramStore.getSpecForSave()
    expect(spec).toBeTruthy()

    diagramStore.loadFromSpec(
      {
        ...spec!,
        is_learning_sheet: true,
        hidden_node_percentage: 0.2,
      },
      diagramStore.type!
    )
    diagramStore.pushHistory('Random blank nodes')

    expect(diagramStore.isLearningSheet).toBe(true)
    expect(diagramStore.hasBlankedLearningSheetNodes()).toBe(true)
    expect(diagramStore.canUndo).toBe(true)

    const blankCountBefore = diagramStore.data?.nodes.filter((node) =>
      diagramStore.isNodeBlankedForLearningSheet(node.id)
    ).length

    tryCollabGuardedUndo()

    expect(diagramStore.hasBlankedLearningSheetNodes()).toBe(false)
    const blankCountAfter = diagramStore.data?.nodes.filter((node) =>
      diagramStore.isNodeBlankedForLearningSheet(node.id)
    ).length
    expect(blankCountAfter).toBeLessThan(blankCountBefore)
  })
})
