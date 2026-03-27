import { type Ref, onMounted, onUnmounted } from 'vue'

import { useDiagramStore } from '@/stores/diagram'

/**
 * Shared composable for measuring actual DOM node dimensions via ResizeObserver.
 * Reports measured width/height to the unified nodeDimensions store on mount,
 * resize, and clears on unmount.
 *
 * @param elementRef - Template ref to the root DOM element of the node
 * @param nodeId - The diagram node id (reactive or static string)
 * @param options.onResize - Optional callback invoked with (width, height) on each measurement
 */
export function useNodeDimensions(
  elementRef: Ref<HTMLElement | null>,
  nodeId: string | Ref<string>,
  options?: {
    onResize?: (width: number, height: number) => void
  }
) {
  const diagramStore = useDiagramStore()
  let resizeObserver: ResizeObserver | null = null
  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  const resolveId = (): string => (typeof nodeId === 'string' ? nodeId : nodeId.value)

  function reportDimensions(): void {
    const el = elementRef.value
    if (!el) return
    const w = el.offsetWidth
    const h = el.offsetHeight
    if (w > 0 && h > 0) {
      diagramStore.setNodeDimensions(resolveId(), w, h)
      options?.onResize?.(w, h)
    }
  }

  function debouncedReport(): void {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(reportDimensions, 50)
  }

  onMounted(() => {
    const el = elementRef.value
    if (!el) return
    reportDimensions()
    resizeObserver = new ResizeObserver(debouncedReport)
    resizeObserver.observe(el)
  })

  onUnmounted(() => {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
    diagramStore.setNodeDimensions(resolveId(), null, null)
  })

  return { reportDimensions }
}
