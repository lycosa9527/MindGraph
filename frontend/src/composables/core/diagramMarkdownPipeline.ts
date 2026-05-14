/**
 * Diagram label measurement uses the same markdown-it + KaTeX pipeline as chat/UI (`useMarkdown`).
 * That module is already pulled into the app bundle by several static imports; a dynamic import
 * here only triggered Vite's “dynamic + static” chunk warning without reducing bundle size.
 *
 * Layout bumps use eventBus (not dynamic import of @/stores) so Vite does not warn about
 * ineffective dynamic imports — the stores barrel is already in the app bundle.
 */
import { eventBus } from '@/composables/core/useEventBus'
import { renderMarkdownForDiagramLabelMeasure } from '@/composables/core/useMarkdown'

let pipelineLoadHandled = false

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
  return true
}

/**
 * Renders diagram label source through the shared markdown + KaTeX pipeline (same output as MindMate/chat).
 */
export function renderMarkdownForDiagramLabelMeasureSync(content: string): string {
  return renderMarkdownForDiagramLabelMeasure(content)
}

function bumpDiagramLayoutRecalc(): void {
  eventBus.emit('diagram:layout_recalc_bump', {})
}

/**
 * Ensures diagram label code has run the same initialization path as before (layout bump on first
 * diagram-driven load). The markdown pipeline module is loaded synchronously with this file.
 *
 * @param bumpLayout - When true (default), bumps diagram layout after the first call so Vue Flow
 *   recomputes with accurate measurements. Set false when calling immediately before loadFromSpec
 *   (full layout refresh follows).
 */
export async function loadDiagramMarkdownPipeline(options?: {
  bumpLayout?: boolean
}): Promise<void> {
  if (pipelineLoadHandled) {
    return
  }
  pipelineLoadHandled = true
  const bumpAfterLoad = options?.bumpLayout !== false
  if (bumpAfterLoad) {
    bumpDiagramLayoutRecalc()
  }
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
