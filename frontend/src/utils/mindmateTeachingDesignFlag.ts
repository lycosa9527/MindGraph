/** Parse and hide MindMate teaching-instruction reply markers. */

export const TEACHING_INSTRUCTION_KIND = 'teaching_instruction' as const

const COMMENT_RE = /<!--\s*mg-reply-kind:\s*([a-z0-9_-]+)\s*-->/i
const COMMENT_STRIP_RE = /<!--\s*mg-reply-kind:[^>]+-->\s*/gi
const BRACKET_RE = /\[\s*mg-reply-kind:\s*([a-z0-9_-]+)\s*\]/i
const BRACKET_STRIP_RE = /\[\s*mg-reply-kind:[^\]]+\]\s*/gi

function normalizeKind(raw: string | undefined | null): string | null {
  if (!raw) {
    return null
  }
  const kind = raw.trim().toLowerCase().replace(/-/g, '_')
  return kind === TEACHING_INSTRUCTION_KIND ? TEACHING_INSTRUCTION_KIND : null
}

export function stripTeachingDesignFlags(content: string): string {
  return (content || '').replace(COMMENT_STRIP_RE, '').replace(BRACKET_STRIP_RE, '').trim()
}

export function parseTeachingInstructionKind(content: string): string | null {
  const comment = COMMENT_RE.exec(content || '')
  const fromComment = normalizeKind(comment?.[1])
  if (fromComment) {
    return fromComment
  }
  const bracket = BRACKET_RE.exec(content || '')
  return normalizeKind(bracket?.[1])
}

export function isTeachingInstructionReply(content: string): boolean {
  return parseTeachingInstructionKind(content) === TEACHING_INSTRUCTION_KIND
}

export function isTeachingInstructionOutputs(outputs: unknown): boolean {
  if (!outputs || typeof outputs !== 'object') {
    return false
  }
  const record = outputs as Record<string, unknown>
  const kind = record.mg_reply_kind ?? record.reply_kind
  if (typeof kind === 'string' && normalizeKind(kind)) {
    return true
  }
  const flag = record.export_word_template
  if (flag === true || flag === 1) {
    return true
  }
  return typeof flag === 'string' && ['1', 'true', 'yes', 'on', TEACHING_INSTRUCTION_KIND].includes(
    flag.trim().toLowerCase()
  )
}
