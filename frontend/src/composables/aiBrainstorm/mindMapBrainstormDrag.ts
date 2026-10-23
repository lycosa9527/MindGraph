export interface MindMapBrainstormDragItem {
  id: string
  text: string
}

export interface MindMapBrainstormDragSession {
  items: MindMapBrainstormDragItem[]
}

let activeSession: MindMapBrainstormDragSession | null = null

export function beginMindMapBrainstormDrag(session: MindMapBrainstormDragSession): void {
  activeSession = session
}

export function endMindMapBrainstormDrag(): void {
  activeSession = null
}

export function getMindMapBrainstormDragSession(): MindMapBrainstormDragSession | null {
  return activeSession
}

/** Hide the browser default drag image so the canvas ghost overlay is visible. */
export function setEmptyNativeDragImage(event: DragEvent): void {
  if (!event.dataTransfer) return
  const img = new Image()
  img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
  event.dataTransfer.setDragImage(img, 0, 0)
}
