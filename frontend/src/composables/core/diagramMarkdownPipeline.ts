/**
 * Lazy-loads the heavy markdown-it + KaTeX pipeline used for diagram labels.
 * Keeps initial canvas / spec-loader chunks free of useMarkdown.ts until math or markdown is needed.
 *
 * Layout bumps use eventBus (not dynamic import of @/stores) so Vite does not warn about
 * ineffective dynamic imports — the stores barrel is already in the app bundle.
 */
import { eventBus } from '@/composables/core/useEventBus'

type RenderMarkdownForMeasure = (content: string) => string

let renderMarkdownForMeasure: RenderMarkdownForMeasure | null = null
let loadPromise: Promise<void> | null = null

/**
 * True when label likely contains markdown or KaTeX (needs rendered DOM width, not source string width).
 */
export function diagramLabelLikelyNeedsRenderedMeasure(text: string): boolean {
  const t = text || ''
  return (
    /\$/.test(t) || /`/.test(t) || /\\[a-zA-Z]/.test(t) || /\*\*[^*]/.test(t) || /__[^_\s]/.test(t)
  )
}

export function isDiagramMarkdownPipelineLoaded(): boolean {
  return renderMarkdownForMeasure !== null
}

/**
 * Sync render after {@link loadDiagramMarkdownPipeline} has resolved.
 */
export function renderMarkdownForDiagramLabelMeasureSync(content: string): string {
  if (!renderMarkdownForMeasure) {
    throw new Error('Diagram markdown pipeline not loaded')
  }
  return renderMarkdownForMeasure(content)
}

function bumpDiagramLayoutRecalc(): void {
  eventBus.emit('diagram:layout_recalc_bump', {})
}

/**
 * Loads markdown-it + KaTeX + DOMPurify (useMarkdown module) once.
 * @param bumpLayout - When true (default), increments diagram layoutRecalcTrigger after first load so Vue Flow recomputes with accurate measurements. Set false when loading immediately before loadFromSpec (full layout refresh follows).
 */
export async function loadDiagramMarkdownPipeline(options?: {
  bumpLayout?: boolean
}): Promise<void> {
  if (renderMarkdownForMeasure) {
    return
  }
  if (!loadPromise) {
    const bumpAfterLoad = options?.bumpLayout !== false
    loadPromise = import('@/composables/core/useMarkdown').then((mod) => {
      renderMarkdownForMeasure = mod.renderMarkdownForDiagramLabelMeasure
      if (bumpAfterLoad) {
        bumpDiagramLayoutRecalc()
      }
    })
  }
  await loadPromise
}

/**
 * Recursively collect string values from a JSON-like spec for math/markdown detection.
 */
export function diagramSpecLikelyNeedsMarkdownPipeline(spec: unknown): boolean {
  if (spec === null || spec === undefined) {
    return false
  }
  if (typeof spec === 'string') {
    return diagramLabelLikelyNeedsRenderedMeasure(spec)
  }
  if (Array.isArray(spec)) {
    for (const item of spec) {
      if (diagramSpecLikelyNeedsMarkdownPipeline(item)) {
        return true
      }
    }
    return false
  }
  if (typeof spec === 'object') {
    for (const value of Object.values(spec as Record<string, unknown>)) {
      if (diagramSpecLikelyNeedsMarkdownPipeline(value)) {
        return true
      }
    }
  }
  return false
}
