/** @mention tokens for MindMate seminar chat (mirrors backend mention.py). */

export interface MindmateMentionCandidate {
  id: string
  name: string
  avatar?: string | null
  kind: 'agent' | 'user'
}

export interface MentionQueryAtCaret {
  at: number
  query: string
}

function isMentionMark(ch: string): boolean {
  return ch === '@' || ch === '＠'
}

export function findMentionQueryAtCaret(text: string, caret: number): MentionQueryAtCaret | null {
  const pos = Math.max(0, Math.min(caret, (text || '').length))
  const source = text || ''
  let at = pos - 1
  while (at >= 0 && !isMentionMark(source.charAt(at))) {
    if (/\s/.test(source.charAt(at))) {
      return null
    }
    at -= 1
  }
  if (at < 0 || !isMentionMark(source.charAt(at))) {
    return null
  }
  if (at > 0 && !/\s/.test(source.charAt(at - 1))) {
    return null
  }
  return {
    at,
    query: source.slice(at + 1, pos),
  }
}

export function insertMentionToken(
  text: string,
  caret: number,
  name: string
): { text: string; caret: number } {
  const found = findMentionQueryAtCaret(text, caret)
  if (!found) {
    return { text, caret }
  }
  const safeName = (name || '').replace(/\*/g, '').trim()
  if (!safeName) {
    return { text, caret }
  }
  const token = `@${safeName} `
  const next = text.slice(0, found.at) + token + text.slice(caret)
  return { text: next, caret: found.at + token.length }
}

export function filterMentionCandidates(
  candidates: readonly MindmateMentionCandidate[],
  query: string
): MindmateMentionCandidate[] {
  const q = query.trim().toLowerCase()
  const rows = candidates.filter((row) => {
    if (!q) {
      return true
    }
    return row.name.toLowerCase().includes(q)
  })
  return rows.slice(0, 12)
}

const MENTION_LEAD = '(?<![A-Za-z0-9_])'
const MENTION_AT = '[@＠]'

function trailingBound(name: string): string {
  const last = name.charAt(name.length - 1)
  if (/[A-Za-z0-9_]/.test(last)) {
    return '(?=$|\\s|[^A-Za-z0-9_])'
  }
  return '(?=$|\\s|[^\\p{L}\\p{N}_])'
}

function mentionPattern(name: string): RegExp | null {
  const cleaned = name
    .trim()
    .replace(/^[@＠]+/, '')
    .replace(/^\*\*|\*\*$/g, '')
    .trim()
  if (!cleaned) {
    return null
  }
  const escaped = cleaned.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(
    `${MENTION_LEAD}${MENTION_AT}(?:\\*\\*)?${escaped}(?:\\*\\*)?${trailingBound(cleaned)}`,
    'iu'
  )
}

export function contentMentionsMindmate(
  content: string,
  agentAliases: readonly string[] = []
): boolean {
  const text = (content || '').trim()
  if (!text) {
    return false
  }
  const aliases = ['MindMate', 'mindmate', ...agentAliases]
  for (const alias of aliases) {
    const pattern = mentionPattern(alias)
    if (pattern?.test(text)) {
      return true
    }
  }
  return false
}

export type CollabRecipientMode = 'mindmate' | 'all'

/** A seminar line asks MindMate only when the text @mentions it. */
export function collabRoutesToMindmate(
  content: string,
  agentAliases: readonly string[] = []
): boolean {
  return contentMentionsMindmate(content, agentAliases)
}

/** Insert @MindMate (or the school agent name) when the draft does not already mention it. */
export function ensureMindmateMention(text: string, name: string): string {
  const agent = name.trim() || 'MindMate'
  const current = text || ''
  if (contentMentionsMindmate(current, [agent])) {
    return current
  }
  const spacer = current.length > 0 && !/\s$/.test(current) ? ' ' : ''
  return `${current}${spacer}@${agent} `
}

function escapeMentionName(name: string): string {
  return name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Append @name at the end of a draft. Skips a second copy when the draft already ends with it. */
export function appendMention(text: string, name: string): string {
  const safe = (name || '')
    .replace(/\*/g, '')
    .trim()
    .replace(/^[@＠]+/u, '')
  const current = text || ''
  if (!safe) {
    return current
  }
  const token = `@${safe}`
  const trailing = new RegExp(`(?:^|\\s)${escapeMentionName(token)}\\s*$`, 'u')
  if (trailing.test(current)) {
    return /\s$/u.test(current) ? current : `${current} `
  }
  const spacer = current.length > 0 && !/\s$/u.test(current) ? ' ' : ''
  return `${current}${spacer}${token} `
}
