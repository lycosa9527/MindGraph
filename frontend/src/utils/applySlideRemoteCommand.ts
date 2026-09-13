import type { SlideRemoteCommandRow } from '@/utils/slideRemoteApi'
import type { MindMapSlideTraversalMode } from '@/utils/mindMapSlides'

export interface SlideRemoteHandlers {
  nextSlide: () => void
  prevSlide: () => void
  toggleAutoPlay: () => void
  autoPlay: boolean
  setTraversalMode: (mode: MindMapSlideTraversalMode) => void
  exitSlideShow: () => void
  startSlides: (diagramId: string) => void
}

function isTraversalMode(value: unknown): value is MindMapSlideTraversalMode {
  return value === 'firstLevel' || value === 'deep'
}

export function applySlideRemoteCommand(
  command: SlideRemoteCommandRow,
  handlers: SlideRemoteHandlers
): void {
  if (command.action === 'next') {
    handlers.nextSlide()
    return
  }
  if (command.action === 'prev') {
    handlers.prevSlide()
    return
  }
  if (command.action === 'quit') {
    handlers.exitSlideShow()
    return
  }
  if (command.action === 'start') {
    const diagramId = typeof command.diagram_id === 'string' ? command.diagram_id.trim() : ''
    if (diagramId) {
      handlers.startSlides(diagramId)
    }
    return
  }
  if (command.action === 'traversal' && isTraversalMode(command.mode)) {
    handlers.setTraversalMode(command.mode)
    return
  }
  if (command.action === 'autoplay') {
    if (typeof command.on === 'boolean') {
      if (command.on !== handlers.autoPlay) {
        handlers.toggleAutoPlay()
      }
      return
    }
    handlers.toggleAutoPlay()
  }
}
