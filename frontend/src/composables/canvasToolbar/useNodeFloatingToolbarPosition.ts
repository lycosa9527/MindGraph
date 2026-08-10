import { nextTick, onUnmounted, ref, watch, type Ref } from 'vue'

const TOOLBAR_GAP_PX = 10

export type FloatingToolbarPosition = {
  left: number
  top: number
  visible: boolean
}

function hiddenPosition(): FloatingToolbarPosition {
  return { left: 0, top: 0, visible: false }
}

export function useNodeFloatingToolbarPosition(options: {
  containerRef: Ref<HTMLElement | null>
  selectedNodeIds: Ref<string[]>
  /** When false, toolbar hides immediately (no rAF delay). */
  enabled: Ref<boolean>
}) {
  const position = ref<FloatingToolbarPosition>(hiddenPosition())

  let rafId = 0

  function hide() {
    cancelAnimationFrame(rafId)
    rafId = 0
    position.value = hiddenPosition()
  }

  function measure() {
    const ids = options.selectedNodeIds.value
    const container = options.containerRef.value
    if (!options.enabled.value || ids.length === 0 || !container) {
      hide()
      return
    }

    let minLeft = Infinity
    let minTop = Infinity
    let maxRight = -Infinity
    let found = 0

    for (const nodeId of ids) {
      const nodeEl = container.querySelector(`.vue-flow__node[data-id="${nodeId}"]`)
      if (!nodeEl) continue
      const nodeRect = nodeEl.getBoundingClientRect()
      minLeft = Math.min(minLeft, nodeRect.left)
      minTop = Math.min(minTop, nodeRect.top)
      maxRight = Math.max(maxRight, nodeRect.right)
      found += 1
    }

    if (found === 0) {
      hide()
      return
    }

    position.value = {
      left: (minLeft + maxRight) / 2,
      top: minTop - TOOLBAR_GAP_PX,
      visible: true,
    }
  }

  function scheduleMeasure() {
    // Suppressors (e.g. open modal) must clear the teleported toolbar in the same tick.
    if (!options.enabled.value || options.selectedNodeIds.value.length === 0) {
      hide()
      return
    }
    cancelAnimationFrame(rafId)
    rafId = requestAnimationFrame(() => {
      void nextTick(measure)
    })
  }

  watch(
    () => [options.selectedNodeIds.value.join('|'), options.enabled.value] as const,
    scheduleMeasure,
    { immediate: true }
  )

  onUnmounted(() => {
    cancelAnimationFrame(rafId)
  })

  return {
    position,
    scheduleMeasure,
  }
}
