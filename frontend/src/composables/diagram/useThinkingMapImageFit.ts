/**
 * Thinking-map nodes with an image use the mind-map rule: the box follows the
 * picture plus the label, instead of the text-only layout size.
 */
import { type CSSProperties, type MaybeRefOrGetter, computed, toValue } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { releaseNodeBoxForImage, thinkingMapNodeHasImage } from '@/utils/nodeImageFrame'

export function useThinkingMapImageFit(nodeId: MaybeRefOrGetter<string>) {
  const diagramStore = useDiagramSession()
  const hasImage = computed(() =>
    thinkingMapNodeHasImage(diagramStore.data, toValue(nodeId), diagramStore.data?.connections)
  )

  function fitBox(style: CSSProperties): CSSProperties {
    return releaseNodeBoxForImage(style, hasImage.value)
  }

  return { hasImage, fitBox }
}
