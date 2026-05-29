/**
 * Lazy-load markdown-it + KaTeX; preloaded on diagram canvas mount and before chat render.
 */
import { ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'

type MarkdownRendererModule = typeof import('@/composables/core/markdownRenderer')

let rendererModule: MarkdownRendererModule | null = null
let loadPromise: Promise<void> | null = null

/** Reactive flag so v-html/computed re-run after the lazy chunk loads. */
export const markdownRendererReady = ref(rendererModule !== null)

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function isMarkdownRendererReady(): boolean {
  return rendererModule !== null
}

/** Load the markdown/KaTeX module once (shared across app). */
export function ensureMarkdownRenderer(): Promise<void> {
  if (rendererModule) {
    markdownRendererReady.value = true
    return Promise.resolve()
  }
  if (!loadPromise) {
    loadPromise = (async () => {
      rendererModule = await import('@/composables/core/markdownRenderer')
      markdownRendererReady.value = true
      eventBus.emit('diagram:layout_recalc_bump', {})
    })()
  }
  return loadPromise
}

/**
 * Render markdown to sanitized HTML. If the renderer is not loaded yet, triggers load and
 * returns escaped plain text until {@link markdownRendererReady} flips (then computeds re-run).
 */
export function renderRichMarkdownHtml(content: string): string {
  if (!rendererModule) {
    void ensureMarkdownRenderer()
    return escapeHtml(content).replace(/\n/g, '<br>')
  }
  return rendererModule.renderRichMarkdownHtmlImpl(content)
}

/** Same pipeline as {@link renderRichMarkdownHtml}; used for diagram label width measurement. */
export function renderMarkdownForDiagramLabelMeasure(content: string): string {
  if (!rendererModule) {
    void ensureMarkdownRenderer()
    return escapeHtml(content).replace(/\n/g, '<br>')
  }
  return rendererModule.renderRichMarkdownHtmlImpl(content)
}

/** Route prefixes where chat/markdown UI is shown (preload before first bubble paints). */
const MARKDOWN_ROUTE_PREFIXES = [
  '/mindmate',
  '/m/mindmate',
  '/workshop-chat',
  '/debateverse',
  '/askonce',
  '/canvas',
  '/m/canvas',
  '/mindgraph',
  '/m/mindgraph',
  '/community',
  '/export-render',
] as const

export function routeUsesRichMarkdown(path: string): boolean {
  return MARKDOWN_ROUTE_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`))
}

/** Fire-and-forget preload when entering a markdown-heavy route. */
export function preloadMarkdownRendererForRoute(path: string): void {
  if (routeUsesRichMarkdown(path)) {
    void ensureMarkdownRenderer()
  }
}
