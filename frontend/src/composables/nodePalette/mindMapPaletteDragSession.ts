export interface MindMapPaletteDragItem {
  id: string
  text: string
}

export interface MindMapPaletteDragSession {
  items: MindMapPaletteDragItem[]
}

let activeSession: MindMapPaletteDragSession | null = null

export function beginMindMapPaletteDrag(session: MindMapPaletteDragSession): void {
  activeSession = session
}

export function endMindMapPaletteDrag(): void {
  activeSession = null
}

export function getMindMapPaletteDragSession(): MindMapPaletteDragSession | null {
  return activeSession
}

/** Hide the browser default drag image so the canvas ghost overlay is visible. */
export function setEmptyNativeDragImage(event: DragEvent): void {
  if (!event.dataTransfer) return
  const img = new Image()
  img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
  event.dataTransfer.setDragImage(img, 0, 0)
}
