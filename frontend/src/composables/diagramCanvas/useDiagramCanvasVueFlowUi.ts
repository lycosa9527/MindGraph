import { type ComputedRef, type Ref, computed } from 'vue'

import { learningSheetPickActive } from '@/composables/mindMap/useLearningSheetCustomMode'
import { useDiagramStore } from '@/stores'
import type { PresentationToolId } from '@/types'

export interface UseDiagramCanvasVueFlowUiOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
  presentationRailOpen: Ref<boolean>
  handToolActive: Ref<boolean>
  panOnDragButtons: Ref<number[] | null | undefined>
  presentationTool: Ref<PresentationToolId>
  presentationHighlighterColor: Ref<string>
  presentationPenColor: Ref<string>
}

export interface UseDiagramCanvasVueFlowUiResult {
  presentationStrokeToolActive: ComputedRef<boolean>
  presentationStrokeColor: ComputedRef<string>
  effectivePanOnDrag: ComputedRef<number[] | boolean>
  presentationToolIsNotTimer: ComputedRef<boolean>
  nodesDraggable: ComputedRef<boolean>
  elementsSelectable: ComputedRef<boolean>
  selectNodesOnDrag: ComputedRef<boolean>
  selectionKeyCode: ComputedRef<boolean | 'Shift'>
  vueFlowBackgroundClasses: ComputedRef<string[]>
}

export function useDiagramCanvasVueFlowUi(
  options: UseDiagramCanvasVueFlowUiOptions
): UseDiagramCanvasVueFlowUiResult {
  const {
    diagramStore,
    presentationRailOpen,
    handToolActive,
    panOnDragButtons,
    presentationTool,
    presentationHighlighterColor,
    presentationPenColor,
  } = options

  const presentationStrokeToolActive = computed(
    () =>
      presentationRailOpen.value &&
      (presentationTool.value === 'highlighter' || presentationTool.value === 'pen')
  )

  const presentationStrokeColor = computed(() =>
    presentationTool.value === 'pen'
      ? presentationPenColor.value
      : presentationHighlighterColor.value
  )

  const effectivePanOnDrag = computed((): number[] | boolean => {
    if (handToolActive.value) {
      return panOnDragButtons.value ?? [0, 1, 2]
    }
    if (presentationStrokeToolActive.value) {
      return false
    }
    // Pointer mode: left-drag box-select; middle mouse pans the canvas.
    return [1]
  })

  const presentationToolIsNotTimer = computed(() => presentationTool.value !== 'timer')

  const nodesDraggable = computed(
    () =>
      !handToolActive.value &&
      !presentationStrokeToolActive.value &&
      diagramStore.type !== 'mindmap' &&
      diagramStore.type !== 'mind_map' &&
      diagramStore.type !== 'tree_map'
  )

  const elementsSelectable = computed(
    () =>
      !handToolActive.value &&
      !presentationStrokeToolActive.value &&
      !learningSheetPickActive.value
  )

  const selectNodesOnDrag = computed(
    () =>
      !handToolActive.value &&
      !presentationStrokeToolActive.value &&
      !learningSheetPickActive.value
  )

  /** `true` = box-select on left drag without holding Shift (Vue Flow API). */
  const selectionKeyCode = computed<boolean | 'Shift'>(() =>
    selectNodesOnDrag.value ? true : 'Shift'
  )

  const vueFlowBackgroundClasses = computed(() => {
    const classes = ['bg-gray-50', 'dark:bg-gray-900']
    const t = diagramStore.type
    if (t !== null && ['circle_map', 'bubble_map', 'double_bubble_map'].includes(t)) {
      classes.push('circle-map-canvas')
    }
    if (t === 'concept_map') {
      classes.push('concept-map-canvas')
    }
    return classes
  })

  return {
    presentationStrokeToolActive,
    presentationStrokeColor,
    effectivePanOnDrag,
    presentationToolIsNotTimer,
    nodesDraggable,
    elementsSelectable,
    selectNodesOnDrag,
    selectionKeyCode,
    vueFlowBackgroundClasses,
  }
}
