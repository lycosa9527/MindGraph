/**
 * Reactive rich-markdown HTML for v-html. Waits for lazy KaTeX/markdown-it load and re-renders when ready.
 */
import { type ComputedRef, computed, onMounted } from 'vue'

import {
  ensureMarkdownRenderer,
  markdownRendererReady,
  renderRichMarkdownHtml,
} from '@/composables/core/lazyMarkdown'

export interface UseRenderedMarkdownOptions {
  /** Strip MindMate-style thinking blocks before render (MindMate bubbles). */
  stripThinkBlocks?: boolean
}

function stripThinkBlocksFromContent(content: string): string {
  return content.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
}

/**
 * Returns sanitized HTML for `source`. Preloads the renderer on mount; recomputes when load finishes.
 */
export function useRenderedMarkdown(
  source: () => string,
  options?: UseRenderedMarkdownOptions
): { html: ComputedRef<string>; ready: ComputedRef<boolean> } {
  onMounted(() => {
    void ensureMarkdownRenderer()
  })

  const ready = computed(() => markdownRendererReady.value)

  const html = computed(() => {
    void markdownRendererReady.value
    let text = source() || ''
    if (options?.stripThinkBlocks) {
      text = stripThinkBlocksFromContent(text)
    }
    if (!text) {
      return ''
    }
    return renderRichMarkdownHtml(text)
  })

  return { html, ready }
}
