/**
 * Markdown + KaTeX HTML for diagram node label display (sanitized via useMarkdown).
 * Loads the heavy pipeline only when the label likely contains math or markdown.
 */
import { type ComputedRef, type Ref, computed, shallowRef, watch } from 'vue'

import {
  diagramLabelLikelyNeedsRenderedMeasure,
  loadDiagramMarkdownPipeline,
  renderMarkdownForDiagramLabelMeasureSync,
} from '@/composables/core/diagramMarkdownPipeline'

export function useDiagramNodeMarkdownDisplay(
  text: ComputedRef<string>,
  enabled: ComputedRef<boolean>
): { richHtml: Ref<string>; needsRichMarkdown: ComputedRef<boolean> } {
  const needsRichMarkdown = computed(
    () => enabled.value && diagramLabelLikelyNeedsRenderedMeasure(text.value)
  )

  const richHtml = shallowRef('')

  watch(
    [() => text.value, needsRichMarkdown],
    async () => {
      if (!needsRichMarkdown.value) {
        richHtml.value = ''
        return
      }
      await loadDiagramMarkdownPipeline()
      try {
        richHtml.value = renderMarkdownForDiagramLabelMeasureSync(text.value)
      } catch {
        richHtml.value = ''
      }
    },
    { immediate: true }
  )

  return { richHtml, needsRichMarkdown }
}
