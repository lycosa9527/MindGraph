export const MIND_MAP_PASTE_MAX_LINES = 50
export const MIND_MAP_PASTE_MAX_LINE_LENGTH = 200

const LIST_PREFIX_RE =
  /^(?:[-*•●○▪▫]\s+|\(\d+\)\s+|\d+[.)）、]\s*)/u

/** Strip common bullet / numbered-list prefixes from a pasted line. */
export function stripListPrefix(line: string): string {
  let current = line.trim()
  for (let i = 0; i < 3 && LIST_PREFIX_RE.test(current); i++) {
    current = current.replace(LIST_PREFIX_RE, '').trim()
  }
  return current
}

export type ParseMultiLinePasteResult = {
  lines: string[]
  truncated: boolean
}

/**
 * Parse clipboard plain text into node labels (one per non-empty line).
 */
export function parseMultiLinePasteText(raw: string): ParseMultiLinePasteResult {
  const normalized = raw.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const parts = normalized.split('\n')
  const lines: string[] = []

  for (const part of parts) {
    const stripped = stripListPrefix(part)
    if (!stripped) continue
    lines.push(stripped.slice(0, MIND_MAP_PASTE_MAX_LINE_LENGTH))
  }

  if (lines.length <= MIND_MAP_PASTE_MAX_LINES) {
    return { lines, truncated: false }
  }

  return {
    lines: lines.slice(0, MIND_MAP_PASTE_MAX_LINES),
    truncated: true,
  }
}
