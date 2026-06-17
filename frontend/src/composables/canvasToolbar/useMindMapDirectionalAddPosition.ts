import { nextTick, onUnmounted, ref, watch, type Ref } from 'vue'

import { MINDMAP_UNDERLINE_STROKE_WIDTH } from '@/config/mindMapGeometry'

/** Match `.mind-map-add-overlay__btn` — used to place bottom handle below the underline. */
const ADD_HANDLE_SIZE = 16
const ADD_HANDLE_HALF = ADD_HANDLE_SIZE / 2
/** Screen-space gap between underline bar and bottom + button (before handle radius). */
const UNDERLINE_BOTTOM_HANDLE_GAP = 10

export type DirectionalAddHandlePosition = {
  direction: 'top' | 'bottom' | 'left' | 'right'
  left: number
  top: number
}

export function useMindMapDirectionalAddPosition(options: {
  containerRef: Ref<HTMLElement | null>
  selectedNodeId: Ref<string | null>
  enabled: Ref<boolean>
}) {
  const handles = ref<DirectionalAddHandlePosition[]>([])
  const visible = ref(false)

  let rafId = 0

  function measure(): void {
    const nodeId = options.selectedNodeId.value
    const container = options.containerRef.value
    if (!options.enabled.value || !nodeId || !container) {
      handles.value = []
      visible.value = false
      return
    }

    const nodeEl = container.querySelector(`.vue-flow__node[data-id="${nodeId}"]`)
    if (!nodeEl) {
      handles.value = []
      visible.value = false
      return
    }

    const rect = nodeEl.getBoundingClientRect()
    if (rect.width < 1 || rect.height < 1) {
      handles.value = []
      visible.value = false
      return
    }

    const cx = rect.left + rect.width / 2
    const cy = rect.top + rect.height / 2
    const isUnderline = nodeEl.querySelector('.mind-map-underline-node') != null
    const lineEl = isUnderline ? nodeEl.querySelector('.mind-map-underline-line') : null
    const lineRect = lineEl?.getBoundingClientRect()
    const anchorY = lineRect
      ? lineRect.top + lineRect.height / 2
      : isUnderline
        ? rect.bottom - MINDMAP_UNDERLINE_STROKE_WIDTH / 2
        : cy
    const bottomTop =
      lineRect != null
        ? lineRect.bottom + UNDERLINE_BOTTOM_HANDLE_GAP + ADD_HANDLE_HALF
        : rect.bottom
    const isTopic = nodeId === 'topic'

    if (isTopic) {
      handles.value = [
        { direction: 'left', left: rect.left, top: anchorY },
        { direction: 'right', left: rect.right, top: anchorY },
      ]
    } else {
      handles.value = [
        { direction: 'top', left: cx, top: rect.top },
        { direction: 'bottom', left: cx, top: bottomTop },
        { direction: 'left', left: rect.left, top: anchorY },
        { direction: 'right', left: rect.right, top: anchorY },
      ]
    }
    visible.value = true
  }

  function scheduleMeasure(): void {
    cancelAnimationFrame(rafId)
    rafId = requestAnimationFrame(() => {
      void nextTick(measure)
    })
  }

  watch(
    () => [options.selectedNodeId.value, options.enabled.value] as const,
    scheduleMeasure,
    { immediate: true }
  )

  onUnmounted(() => {
    cancelAnimationFrame(rafId)
  })

  return {
    handles,
    visible,
    scheduleMeasure,
  }
}
