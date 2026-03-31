import { type Ref, onMounted, onUnmounted } from 'vue'

import { useDiagramStore } from '@/stores/diagram'

/**
 * Shared composable for measuring actual DOM node dimensions via ResizeObserver.
 * Reports measured width/height to the unified nodeDimensions store on mount,
 * resize, and clears on unmount.
 *
 * ResizeObserver invokes the callback when layout size changes; we coalesce
 * bursts with requestAnimationFrame (one read per frame) instead of a timer debounce.
 *
 * @param elementRef - Template ref to the root DOM element of the node
 * @param nodeId - The diagram node id (reactive or static string)
 * @param options.onResize - Optional callback invoked with (width, height) on each measurement
 * @param options.observeRoot - When false, skip ResizeObserver and initial report on the root
 *   (use when Pinia sizes come from a child, e.g. rendered KaTeX inside a fixed-size circle).
 */
export function useNodeDimensions(
  elementRef: Ref<HTMLElement | null>,
  nodeId: string | Ref<string>,
  options?: {
    onResize?: (width: number, height: number) => void
    observeRoot?: boolean
  }
) {
  const diagramStore = useDiagramStore()
  let resizeObserver: ResizeObserver | null = null
  let rafId: number | null = null

  const resolveId = (): string => (typeof nodeId === 'string' ? nodeId : nodeId.value)

  function reportDimensions(): void {
    const el = elementRef.value
    if (!el) return
    const w = el.offsetWidth
    const h = el.offsetHeight
    if (w > 0 && h > 0) {
      const id = resolveId()
      diagramStore.setNodeDimensions(id, w, h)
      options?.onResize?.(w, h)
    }
  }

  function scheduleReportFromResize(): void {
    if (typeof requestAnimationFrame !== 'function') {
      reportDimensions()
      return
    }
    if (rafId !== null) return
    rafId = requestAnimationFrame(() => {
      rafId = null
      reportDimensions()
    })
  }

  onMounted(() => {
    const el = elementRef.value
    if (!el) return
    if (options?.observeRoot === false) {
      return
    }
    reportDimensions()
    resizeObserver = new ResizeObserver(() => {
      scheduleReportFromResize()
    })
    resizeObserver.observe(el)
  })

  onUnmounted(() => {
    if (rafId !== null && typeof cancelAnimationFrame === 'function') {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
    diagramStore.setNodeDimensions(resolveId(), null, null)
  })

  return { reportDimensions }
}
