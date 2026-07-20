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
    presentationPointerEditMode: ref(false),
    presentationHandPanMode: ref(false),
    panOnDragButtons: ref<number[] | null>(null),
    presentationTool: ref<'pointer' | 'highlighter' | 'pen' | 'timer'>('pointer'),
    presentationHighlighterColor: ref('#fef08a'),
    presentationPenColor: ref('#ef4444'),
    ...overrides,
  }
}

describe('useDiagramCanvasVueFlowUi', () => {
  it('keeps desktop pointer-mode always-on marquee (new canvas)', () => {
    learningSheetPickActive.value = false
    const ui = useDiagramCanvasVueFlowUi(buildUiOptions())
    expect(ui.selectNodesOnDrag.value).toBe(true)
    expect(ui.selectionKeyCode.value).toBe(true)
    expect(ui.effectivePanOnDrag.value).toEqual([1])
    expect(ui.elementsSelectable.value).toBe(true)
  })

  it('disables marquee and VF pan when mobile panOnDragButtons are set', () => {
    learningSheetPickActive.value = false
    const ui = useDiagramCanvasVueFlowUi(
      buildUiOptions({
        panOnDragButtons: ref<number[] | null>([0, 1, 2]),
      })
    )
    expect(ui.selectNodesOnDrag.value).toBe(false)
    expect(ui.selectionKeyCode.value).toBe(null)
    expect(ui.effectivePanOnDrag.value).toBe(false)
    // Tap-to-select nodes must still work
    expect(ui.elementsSelectable.value).toBe(true)
  })

  it('uses null (Vue Flow default Shift) when drag-select is disabled', () => {
    learningSheetPickActive.value = true
    const ui = useDiagramCanvasVueFlowUi(buildUiOptions())
    expect(ui.selectNodesOnDrag.value).toBe(false)
    expect(ui.selectionKeyCode.value).toBe(null)
  })

  it('hand tool pans with all buttons and turns selection off', () => {
    learningSheetPickActive.value = false
    const ui = useDiagramCanvasVueFlowUi(
      buildUiOptions({
        handToolActive: ref(true),
      })
    )
    expect(ui.effectivePanOnDrag.value).toEqual([0, 1, 2])
    expect(ui.selectNodesOnDrag.value).toBe(false)
    expect(ui.elementsSelectable.value).toBe(false)
  })
})
