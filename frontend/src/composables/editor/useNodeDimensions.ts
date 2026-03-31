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

  function logCenterAlignment(el: HTMLElement, id: string): void {
    const nodeRect = el.getBoundingClientRect()
    const nodeCenterY = nodeRect.top + nodeRect.height / 2

    const katexEl = el.querySelector('.katex-html') as HTMLElement | null
    if (!katexEl) return

    const katexRect = katexEl.getBoundingClientRect()
    const katexCenterY = katexRect.top + katexRect.height / 2
    const deltaY = katexCenterY - nodeCenterY

    const mdEl = el.querySelector('.diagram-node-md') as HTMLElement | null
    const mdRect = mdEl?.getBoundingClientRect()
    const katexParent = el.querySelector('.katex') as HTMLElement | null
    const katexParentRect = katexParent?.getBoundingClientRect()
    const katexParentStyle = katexParent ? getComputedStyle(katexParent) : null

    let pInfo = ''
    if (mdEl) {
      const pEls = mdEl.querySelectorAll('p')
      pEls.forEach((p, i) => {
        const pRect = p.getBoundingClientRect()
        const pStyle = getComputedStyle(p)
        pInfo +=
          `  <p>[${i}]: top=${pRect.top.toFixed(1)} h=${pRect.height.toFixed(1)} ` +
          `margin=${pStyle.margin} lineHeight=${pStyle.lineHeight} children=${p.childNodes.length}\n`
      })
      if (pEls.length === 0) {
        pInfo = `  <p>: NONE (direct children: ${mdEl.childNodes.length})\n`
      }
    }

    const displayEl = el.querySelector('.inline-edit-display') as HTMLElement | null
    const displayRect = displayEl?.getBoundingClientRect()
    const displayStyle = displayEl ? getComputedStyle(displayEl) : null

    const inlineEditEl = el.querySelector('.inline-editable-text') as HTMLElement | null
    const inlineEditRect = inlineEditEl?.getBoundingClientRect()

    console.log(
      `[NodeLayout:Align] id="${id}"\n` +
        `  node:      top=${nodeRect.top.toFixed(1)} h=${nodeRect.height.toFixed(1)} w=${nodeRect.width.toFixed(1)} centerY=${nodeCenterY.toFixed(1)}\n` +
        `  .inline-editable-text: top=${inlineEditRect?.top.toFixed(1)} h=${inlineEditRect?.height.toFixed(1)}\n` +
        `  .inline-edit-display: top=${displayRect?.top.toFixed(1)} h=${displayRect?.height.toFixed(1)} maxW=${displayStyle?.maxWidth} display=${displayStyle?.display}\n` +
        `  .diagram-node-md: top=${mdRect?.top.toFixed(1)} h=${mdRect?.height.toFixed(1)} w=${mdRect?.width.toFixed(1)} display=${mdEl ? getComputedStyle(mdEl).display : ''}\n` +
        pInfo +
        `  .katex:    top=${katexParentRect?.top.toFixed(1)} h=${katexParentRect?.height.toFixed(1)} w=${katexParentRect?.width.toFixed(1)} display=${katexParentStyle?.display} vAlign=${katexParentStyle?.verticalAlign}\n` +
        `  .katex-html: top=${katexRect.top.toFixed(1)} h=${katexRect.height.toFixed(1)} w=${katexRect.width.toFixed(1)} centerY=${katexCenterY.toFixed(1)}\n` +
        `  ΔcenterY = ${deltaY.toFixed(1)}px (formula ${deltaY > 0.5 ? 'BELOW' : deltaY < -0.5 ? 'ABOVE' : '≈ CENTERED'})\n` +
        `  innerHTML(200): ${mdEl?.innerHTML?.slice(0, 200)}`
    )
  }

  function reportDimensions(): void {
    const el = elementRef.value
    if (!el) return
    const w = el.offsetWidth
    const h = el.offsetHeight
    if (w > 0 && h > 0) {
      const id = resolveId()
      console.log(`[NodeLayout:DOM] ResizeObserver → id="${id}" offsetW=${w} offsetH=${h}`)
      diagramStore.setNodeDimensions(id, w, h)
      options?.onResize?.(w, h)
      logCenterAlignment(el, id)
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
