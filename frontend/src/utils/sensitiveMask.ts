/**
 * Mask the middle of a string for safe display (aligned with server `_mask_secret` in mindbot API).
 */
export function maskSensitiveDisplay(secret: string, head = 4, tail = 4): string {
  const text = (secret ?? '').trim()
  if (!text) {
    return ''
  }
  const length = text.length
  if (length <= head + tail) {
    if (length <= 1) {
      return '•'
    }
    if (length === 2) {
      return `${text[0]}•`
    }
    return `${text[0]}${'•'.repeat(length - 2)}${text[length - 1]}`
  }
  const mid = Math.min(length - head - tail, 12)
  return `${text.slice(0, head)}${'•'.repeat(mid)}${text.slice(-tail)}`
}
