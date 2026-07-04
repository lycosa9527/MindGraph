import { ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { useDiagramCanvasVueFlowUi } from '@/composables/diagramCanvas/useDiagramCanvasVueFlowUi'
import { learningSheetPickActive } from '@/composables/mindMap/useLearningSheetCustomMode'

function buildUiOptions(overrides: Partial<Parameters<typeof useDiagramCanvasVueFlowUi>[0]> = {}) {
  return {
    diagramStore: {
      type: 'mindmap',
    } as ReturnType<typeof import('@/stores').useDiagramStore>,
    presentationRailOpen: ref(false),
    handToolActive: ref(false),
    presentationPointerEditMode: ref(true),
    presentationHandPanMode: ref(false),
    panOnDragButtons: ref<number[] | null>([0, 1, 2]),
    presentationTool: ref<'pointer' | 'highlighter' | 'pen' | 'timer'>('pointer'),
    presentationHighlighterColor: ref('#fef08a'),
    presentationPenColor: ref('#ef4444'),
    ...overrides,
  }
}

describe('useDiagramCanvasVueFlowUi', () => {
  it('uses true for selectionKeyCode when drag-select is enabled', () => {
    learningSheetPickActive.value = false
    const ui = useDiagramCanvasVueFlowUi(buildUiOptions())
    expect(ui.selectNodesOnDrag.value).toBe(true)
    expect(ui.selectionKeyCode.value).toBe(true)
  })

  it('uses null (Vue Flow default Shift) when drag-select is disabled', () => {
    learningSheetPickActive.value = true
    const ui = useDiagramCanvasVueFlowUi(buildUiOptions())
    expect(ui.selectNodesOnDrag.value).toBe(false)
    expect(ui.selectionKeyCode.value).toBe(null)
  })
})
