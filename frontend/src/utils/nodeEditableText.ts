/** True when the node label is only whitespace (intentional blank placeholder). */
export function isWhitespaceOnlyNodeText(text: string | undefined | null): boolean {
  if (text == null || text.length === 0) return false
  return text.trim().length === 0
}

/**
 * Resolve inline editor text for persistence.
 * - Normal content: trim surrounding whitespace.
 * - Whitespace-only: keep as a blank placeholder (do not trim away).
 * - Truly empty: null (caller should cancel the edit).
 */
export function resolveInlineNodeTextForSave(
  raw: string,
  minLength: number,
  maxLength: number
): string | null {
  const trimmed = raw.trim()
  if (trimmed.length >= minLength) {
    return trimmed.slice(0, maxLength)
  }
  if (isWhitespaceOnlyNodeText(raw)) {
    return raw.slice(0, maxLength)
  }
  if (raw.length >= minLength) {
    return raw.slice(0, maxLength)
  }
  return null
}
