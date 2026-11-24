/**
 * Canvas ribbon asks MindMate with the same prompt as a suggestion bubble.
 * The panel mounts after open, so the prompt waits until that handler exists.
 */
type CanvasSuggestionHandler = (text: string) => void

let pending: string | null = null
let handler: CanvasSuggestionHandler | null = null

export function requestCanvasSuggestion(text: string): void {
  const trimmed = text.trim()
  if (!trimmed) return
  pending = trimmed
  flushCanvasSuggestion()
}

export function bindCanvasSuggestion(next: CanvasSuggestionHandler): () => void {
  handler = next
  flushCanvasSuggestion()
  return () => {
    if (handler === next) handler = null
  }
}

function flushCanvasSuggestion(): void {
  if (!pending || !handler) return
  const text = pending
  pending = null
  handler(text)
}
