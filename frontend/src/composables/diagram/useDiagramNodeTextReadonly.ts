/**
 * Shared readonly gate for InlineEditableText on diagram nodes.
 * Combines learning-sheet hide, presentation lock, and session.isReadonly (Showcase).
 */
import { computed, type ComputedRef } from 'vue'

import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'

import { useDiagramSession } from './useDiagramSession'

export function useDiagramNodeTextReadonly(
  isHidden: () => boolean
): ComputedRef<boolean> {
  const diagramStore = useDiagramSession()
  return computed(() => {
    if (diagramPresentationReadOnlyRef.value || Boolean(diagramStore.isReadonly)) {
      return true
    }
    // Learning-sheet blanks are fill-in fields; keep hidden nodes locked only outside worksheet mode.
    if (isHidden() && !diagramStore.isLearningSheet) {
      return true
    }
    return false
  })
}
