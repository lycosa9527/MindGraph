import type { Connection, DiagramNode } from '@/types'

function normalizeLabel(text: string): string {
  return text.trim().toLowerCase()
}

/**
 * Resolve a mind-map node id for Kitty branch auto-complete by label.
 * Prefers the last matching non-topic node (newest branch wins on duplicates).
 */
export function findMindMapNodeIdByLabel(
  nodes: DiagramNode[] | undefined,
  connections: Connection[] | undefined,
  label: string
): string | null {
  const wanted = normalizeLabel(label)
  if (!wanted || !nodes?.length) {
    return null
  }

  const matches = nodes.filter((node) => {
    if (!node?.id || node.id === 'topic') {
      return false
    }
    return normalizeLabel(String(node.text ?? '')) === wanted
  })
  if (matches.length === 0) {
    return null
  }
  if (matches.length === 1 || !connections?.length) {
    return matches[matches.length - 1]?.id ?? null
  }

  const parentByChild = new Map<string, string>()
  for (const conn of connections) {
    if (conn?.source && conn?.target) {
      parentByChild.set(conn.target, conn.source)
    }
  }
  const topicChildren = matches.filter((node) => parentByChild.get(node.id) === 'topic')
  const pool = topicChildren.length > 0 ? topicChildren : matches
  return pool[pool.length - 1]?.id ?? null
}
