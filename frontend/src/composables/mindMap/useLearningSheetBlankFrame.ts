/**
 * DOM lock for a knocked-out thinking-map node. Mind maps lock their own boxes.
 */
import { type CSSProperties, type MaybeRefOrGetter, computed, toValue } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { learningSheetBlankFrameStyle } from '@/utils/learningSheetBlankFrame'

export function useLearningSheetBlankFrame(
  nodeId: MaybeRefOrGetter<string>,
  data: MaybeRefOrGetter<object | undefined>
) {
  const diagramStore = useDiagramSession()
  return computed((): CSSProperties => {
    const id = toValue(nodeId)
    if (!diagramStore.isLearningSheet || !diagramStore.isNodeBlankedForLearningSheet(id)) {
      return {}
    }
    return learningSheetBlankFrameStyle(toValue(data))
  })
}
