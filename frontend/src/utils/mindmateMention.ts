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

export function findMentionQueryAtCaret(text: string, caret: number): MentionQueryAtCaret | null {
  const pos = Math.max(0, Math.min(caret, (text || '').length))
  const source = text || ''
  let at = pos - 1
  while (at >= 0 && source.charAt(at) !== '@') {
    if (/\s/.test(source.charAt(at))) {
      return null
    }
    at -= 1
  }
  if (at < 0 || source.charAt(at) !== '@') {
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

function mentionPattern(name: string): RegExp | null {
  const cleaned = name.trim().replace(/^@+/, '').replace(/^\*\*|\*\*$/g, '').trim()
  if (!cleaned) {
    return null
  }
  const escaped = cleaned.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`@(?:\\*\\*)?${escaped}(?:\\*\\*)?(?=$|\\s|[^\\p{L}\\p{N}_])`, 'iu')
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
