/**
 * MindMate collab @-mention helpers (generic chat vs ask AI).
 */

export function collabMessageMentionsMindmate(text: string, agentName?: string | null): boolean {
  const trimmed = text.trim()
  if (!trimmed) {
    return false
  }
  const lower = trimmed.toLowerCase()
  if (lower.includes('@mindmate')) {
    return true
  }
  const alias = (agentName || '').trim()
  if (alias && lower.includes(`@${alias.toLowerCase()}`)) {
    return true
  }
  return false
}

export function insertMindmateMention(current: string, agentName: string): string {
  const label = agentName.trim() || 'MindMate'
  const mention = `@${label} `
  if (!current.trim()) {
    return mention
  }
  if (current.endsWith(' ') || current.endsWith('\n')) {
    return `${current}${mention}`
  }
  return `${current} ${mention}`
}
