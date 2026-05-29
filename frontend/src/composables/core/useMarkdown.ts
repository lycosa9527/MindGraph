/**
 * Markdown rendering composable (markdown-it + KaTeX loaded on demand via lazyMarkdown.ts).
 */
import {
  ensureMarkdownRenderer,
  markdownRendererReady,
  preloadMarkdownRendererForRoute,
  renderMarkdownForDiagramLabelMeasure,
  renderRichMarkdownHtml,
  routeUsesRichMarkdown,
} from '@/composables/core/lazyMarkdown'

export {
  ensureMarkdownRenderer,
  markdownRendererReady,
  preloadMarkdownRendererForRoute,
  renderMarkdownForDiagramLabelMeasure,
  renderRichMarkdownHtml,
  routeUsesRichMarkdown,
}

export function useMarkdown() {
  void ensureMarkdownRenderer()

  function render(content: string): string {
    return renderRichMarkdownHtml(content)
  }

  return { render, ensureReady: ensureMarkdownRenderer }
}
