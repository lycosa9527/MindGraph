/**
 * Viewport for one 演讲模式 slide: overview fills the window; branches zoom to nodes.
 */
import { eventBus } from '@/composables/core/useEventBus'
import type { MindMapSlide } from '@/utils/mindMapSlides'

export const MIND_MAP_SLIDE_TRANSITION_MS = 920

export function emitMindMapSlideViewportFit(
  slide: Pick<MindMapSlide, 'kind' | 'focusNodeIds'>
): void {
  if (slide.kind === 'overview') {
    eventBus.emit('view:fit_to_canvas_requested', {
      animate: true,
      userInitiated: true,
    })
    return
  }
  eventBus.emit('view:fit_to_nodes_requested', {
    nodeIds: slide.focusNodeIds,
    animate: true,
    duration: MIND_MAP_SLIDE_TRANSITION_MS,
    padding: slide.focusNodeIds.length <= 1 ? 0.45 : 0.38,
    userInitiated: true,
  })
}
