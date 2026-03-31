/**
 * Markdown + KaTeX HTML for diagram node label display (sanitized via useMarkdown).
 */
import { type ComputedRef, computed } from 'vue'

import { useMarkdown } from '@/composables/core/useMarkdown'

export function useDiagramNodeMarkdownDisplay(
  text: ComputedRef<string>,
  enabled: ComputedRef<boolean>
): ComputedRef<string> {
  const { render } = useMarkdown()
  return computed(() => {
    if (!enabled.value) {
      return ''
    }
    const s = text.value || ''
    return render(s)
  })
}
