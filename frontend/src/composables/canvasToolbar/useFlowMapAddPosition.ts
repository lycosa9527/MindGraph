import { type Ref, nextTick, onUnmounted, ref, watch } from 'vue'

import {
  type FlowMapAddHandleLayout,
  layoutFlowMapAddHandles,
  resolveFlowMapAddSelectionKind,
} from '@/utils/flowMapAddHandles'
import type { FlowSubstepArrangement } from '@/utils/flowMapSubstepArrangement'

/** Match `.flow-map-add-overlay__btn` base size (before e-blackboard scale). */
const ADD_HANDLE_SIZE = 16

export type FlowMapAddHandlePosition = FlowMapAddHandleLayout

export function useFlowMapAddPosition(options: {
  containerRef: Ref<HTMLElement | null>
  selectedNodeId: Ref<string | null>
  selectionKind: Ref<ReturnType<typeof resolveFlowMapAddSelectionKind>>
  orientation: Ref<'horizontal' | 'vertical'>
  /** Row vs stack packing under each step (drives substep + axis). */
  substepArrangement: Ref<FlowSubstepArrangement>
  /** When false, handles hide immediately (no rAF delay). */
  enabled: Ref<boolean>
  /** 1 = default; 2 = classroom board. */
  controlScale?: Ref<number>
}) {
  const handles = ref<FlowMapAddHandlePosition[]>([])
  const visible = ref(false)

  let rafId = 0

  function hide(): void {
    cancelAnimationFrame(rafId)
    rafId = 0
    handles.value = []
    visible.value = false
  }

  function measure(): void {
    const nodeId = options.selectedNodeId.value
    const kind = options.selectionKind.value
    const container = options.containerRef.value
    if (!options.enabled.value || !nodeId || !kind || !container) {
      hide()
      return
    }

    const nodeEl = container.querySelector(`.vue-flow__node[data-id="${nodeId}"]`)
    if (!nodeEl) {
      hide()
      return
    }

    const rect = nodeEl.getBoundingClientRect()
    if (rect.width < 1 || rect.height < 1) {
      hide()
      return
    }

    const scale = options.controlScale?.value ?? 1
    const inset = (ADD_HANDLE_SIZE * scale) / 2
    const padded = {
      left: rect.left - inset * 0.15,
      top: rect.top,
      right: rect.right + inset * 0.15,
      bottom: rect.bottom + inset * 0.2,
      width: rect.width,
      height: rect.height,
    }
    handles.value = layoutFlowMapAddHandles(
      kind,
      options.orientation.value,
      padded,
      options.substepArrangement.value
    )
    visible.value = handles.value.length > 0
  }

  function scheduleMeasure(): void {
    if (!options.enabled.value || !options.selectedNodeId.value) {
      hide()
      return
    }
    cancelAnimationFrame(rafId)
    rafId = requestAnimationFrame(() => {
      void nextTick(measure)
    })
  }

  watch(
    () =>
      [
        options.selectedNodeId.value,
        options.selectionKind.value,
        options.orientation.value,
        options.substepArrangement.value,
        options.enabled.value,
        options.controlScale?.value ?? 1,
      ] as const,
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
