const STORAGE_KEY = 'mg_slide_remote_canvas_drain'
const STALE_MS = 1500

export function touchSlideRemoteCanvasDrain(): void {
  localStorage.setItem(STORAGE_KEY, String(Date.now()))
}

export function clearSlideRemoteCanvasDrain(): void {
  localStorage.removeItem(STORAGE_KEY)
}

export function slideRemoteCanvasIsDraining(): boolean {
  const raw = Number(localStorage.getItem(STORAGE_KEY) || 0)
  if (!Number.isFinite(raw) || raw <= 0) {
    return false
  }
  return Date.now() - raw < STALE_MS
}
