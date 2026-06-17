import { nextTick, onUnmounted, ref, watch, type Ref } from 'vue'

const TOOLBAR_GAP_PX = 10

export type FloatingToolbarPosition = {
  left: number
  top: number
  visible: boolean
}

export function useNodeFloatingToolbarPosition(options: {
  containerRef: Ref<HTMLElement | null>
  selectedNodeIds: Ref<string[]>
  enabled: Ref<boolean>
}) {
  const position = ref<FloatingToolbarPosition>({
    left: 0,
    top: 0,
    visible: false,
  })

  let rafId = 0

  function measure() {
    const ids = options.selectedNodeIds.value
    const container = options.containerRef.value
    if (!options.enabled.value || ids.length === 0 || !container) {
      position.value = { left: 0, top: 0, visible: false }
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
      position.value = { left: 0, top: 0, visible: false }
      return
    }

    position.value = {
      left: (minLeft + maxRight) / 2,
      top: minTop - TOOLBAR_GAP_PX,
      visible: true,
    }
  }

  function scheduleMeasure() {
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
