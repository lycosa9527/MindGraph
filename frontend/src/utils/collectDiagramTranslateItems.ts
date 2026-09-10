export type DiagramTranslateItem = {
  itemId: string
  text: string
  kind: 'node' | 'connection'
}

type TranslateNodeLike = {
  id?: unknown
  text?: unknown
  data?: { label?: unknown } | null
}

type TranslateConnectionLike = {
  id?: unknown
  label?: unknown
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

function readId(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null
  }
  const id = value.trim()
  return id.length > 0 ? id : null
}

function collectNodeItem(node: TranslateNodeLike): DiagramTranslateItem | null {
  const itemId = readId(node.id)
  if (!itemId) {
    return null
  }
  const fromData = asObject(node.data)
  const text = String(node.text ?? fromData?.label ?? '').trim()
  if (!text) {
    return null
  }
  return { itemId, text, kind: 'node' }
}

function collectConnectionItem(conn: TranslateConnectionLike): DiagramTranslateItem | null {
  const itemId = readId(conn.id)
  if (!itemId) {
    return null
  }
  const text = String(conn.label ?? '').trim()
  if (!text) {
    return null
  }
  return { itemId, text, kind: 'connection' }
}

/**
 * Collect non-empty node / connection labels from a live diagram or a saved spec snapshot.
 */
export function collectDiagramTranslateItems(
  source: {
    nodes?: unknown
    connections?: unknown
  } | null
): DiagramTranslateItem[] {
  const out: DiagramTranslateItem[] = []
  const nodes = Array.isArray(source?.nodes) ? source.nodes : []
  for (const node of nodes) {
    const item = collectNodeItem(asObject(node) ?? {})
    if (item) {
      out.push(item)
    }
  }
  const connections = Array.isArray(source?.connections) ? source.connections : []
  for (const conn of connections) {
    const item = collectConnectionItem(asObject(conn) ?? {})
    if (item) {
      out.push(item)
    }
  }
  return out
}
