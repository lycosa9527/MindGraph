import { type ComputedRef, type Ref, computed } from 'vue'

import { DEFAULT_PRESENTATION_PEN_COLOR } from '@/config/presentationHighlighter'
import { useDiagramStore } from '@/stores'
import type { PresentationToolId } from '@/types'

export interface UseDiagramCanvasVueFlowUiOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
  presentationRailOpen: Ref<boolean>
  handToolActive: Ref<boolean>
  panOnDragButtons: Ref<number[] | null | undefined>
  presentationTool: Ref<PresentationToolId>
  presentationHighlighterColor: Ref<string>
}

export interface UseDiagramCanvasVueFlowUiResult {
  presentationStrokeToolActive: ComputedRef<boolean>
  presentationStrokeColor: ComputedRef<string>
  effectivePanOnDrag: ComputedRef<number[]>
  presentationToolIsNotTimer: ComputedRef<boolean>
  nodesDraggable: ComputedRef<boolean>
  elementsSelectable: ComputedRef<boolean>
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
  } = options

  const presentationStrokeToolActive = computed(
    () =>
      presentationRailOpen.value &&
      (presentationTool.value === 'highlighter' || presentationTool.value === 'pen')
  )

  const presentationStrokeColor = computed(() =>
    presentationTool.value === 'pen'
      ? DEFAULT_PRESENTATION_PEN_COLOR
      : presentationHighlighterColor.value
  )

  const effectivePanOnDrag = computed((): number[] => {
    const base = panOnDragButtons.value ?? (handToolActive.value ? [0, 1, 2] : [1, 2])
    if (!presentationRailOpen.value) {
      return base
    }
    const withoutRight = base.filter((b) => b !== 2)
    return withoutRight.length > 0 ? withoutRight : [1]
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
    () => !handToolActive.value && !presentationStrokeToolActive.value
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
    vueFlowBackgroundClasses,
  }
}
