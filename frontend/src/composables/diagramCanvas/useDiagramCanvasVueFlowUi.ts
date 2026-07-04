import { type ComputedRef, type Ref, computed } from 'vue'

import { learningSheetPickActive } from '@/composables/mindMap/useLearningSheetCustomMode'
import { useDiagramStore } from '@/stores'
import type { PresentationToolId } from '@/types'

export interface UseDiagramCanvasVueFlowUiOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
  presentationRailOpen: Ref<boolean>
  handToolActive: Ref<boolean>
  presentationPointerEditMode: Ref<boolean>
  presentationHandPanMode: Ref<boolean>
  panOnDragButtons: Ref<number[] | null | undefined>
  presentationTool: Ref<PresentationToolId>
  presentationHighlighterColor: Ref<string>
  presentationPenColor: Ref<string>
}

export interface UseDiagramCanvasVueFlowUiResult {
  presentationStrokeToolActive: ComputedRef<boolean>
  presentationStrokeColor: ComputedRef<string>
  presentationDiagramEditLocked: ComputedRef<boolean>
  effectivePanOnDrag: ComputedRef<number[] | boolean>
  presentationToolIsNotTimer: ComputedRef<boolean>
  nodesDraggable: ComputedRef<boolean>
  elementsSelectable: ComputedRef<boolean>
  selectNodesOnDrag: ComputedRef<boolean>
  selectionKeyCode: ComputedRef<boolean | null>
  vueFlowBackgroundClasses: ComputedRef<string[]>
}

export function useDiagramCanvasVueFlowUi(
  options: UseDiagramCanvasVueFlowUiOptions
): UseDiagramCanvasVueFlowUiResult {
  const {
    diagramStore,
    presentationRailOpen,
    handToolActive,
    presentationPointerEditMode,
    presentationHandPanMode,
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

  /** Block diagram edits unless presentation pointer (default edit) mode is active. */
  const presentationDiagramEditLocked = computed(
    () => presentationRailOpen.value && !presentationPointerEditMode.value
  )

  const presentationStrokeColor = computed(() =>
    presentationTool.value === 'pen'
      ? presentationPenColor.value
      : presentationHighlighterColor.value
  )

  const effectivePanOnDrag = computed((): number[] | boolean => {
    if (presentationHandPanMode.value) {
      return panOnDragButtons.value ?? [0, 1, 2]
    }
    if (presentationPointerEditMode.value) {
      return [1]
    }
    if (handToolActive.value) {
      return panOnDragButtons.value ?? [0, 1, 2]
    }
    if (presentationStrokeToolActive.value) {
      return false
    }
    return [1]
  })

  const presentationToolIsNotTimer = computed(() => presentationTool.value !== 'timer')

  const nodesDraggable = computed(
    () =>
      !presentationDiagramEditLocked.value &&
      !handToolActive.value &&
      !presentationHandPanMode.value &&
      !presentationStrokeToolActive.value &&
      diagramStore.type !== 'mindmap' &&
      diagramStore.type !== 'mind_map' &&
      diagramStore.type !== 'tree_map'
  )

  const elementsSelectable = computed(() => {
    if (learningSheetPickActive.value) return false
    if (presentationStrokeToolActive.value) return false
    if (presentationPointerEditMode.value) return true
    if (presentationDiagramEditLocked.value) return false
    if (handToolActive.value || presentationHandPanMode.value) return false
    return true
  })

  const selectNodesOnDrag = computed(() => {
    if (learningSheetPickActive.value) return false
    if (presentationStrokeToolActive.value) return false
    if (presentationPointerEditMode.value) return true
    if (presentationDiagramEditLocked.value) return false
    if (handToolActive.value || presentationHandPanMode.value) return false
    return true
  })

  // Vue Flow 1.48 runtime prop check accepts boolean | null only (not key strings).
  // null keeps the library default (Shift) for hand-tool / pick modes where drag-select is off.
  const selectionKeyCode = computed<boolean | null>(() =>
    selectNodesOnDrag.value ? true : null
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
    presentationDiagramEditLocked,
    effectivePanOnDrag,
    presentationToolIsNotTimer,
    nodesDraggable,
    elementsSelectable,
    selectNodesOnDrag,
    selectionKeyCode,
    vueFlowBackgroundClasses,
  }
}
