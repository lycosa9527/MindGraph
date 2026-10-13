export type DiagramTranslateItem = {
  itemId: string
  text: string
  kind: 'node' | 'connection'
}

type TranslateNodeLike = {
  id?: unknown
  text?: unknown
  textSecondary?: unknown
  data?: { label?: unknown; labelSecondary?: unknown } | null
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

function readSecondaryLine(node: TranslateNodeLike, data: Record<string, unknown> | null): string {
  const fromNode = typeof node.textSecondary === 'string' ? node.textSecondary.trim() : ''
  if (fromNode) {
    return fromNode
  }
  const fromData = data?.labelSecondary
  return typeof fromData === 'string' ? fromData.trim() : ''
}

/**
 * Dual-language nodes keep the gloss on `textSecondary`.
 * If that gloss was also pasted into the primary field, send only the primary lines.
 */
function primaryLabelText(text: string, secondary: string): string {
  if (!secondary) {
    return text
  }
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
  if (lines.length < 2) {
    return text
  }
  const kept = lines.filter((line) => line !== secondary)
  if (kept.length === 0 || kept.length === lines.length) {
    return text
  }
  return kept.join('\n')
}

function collectNodeItem(node: TranslateNodeLike): DiagramTranslateItem | null {
  const itemId = readId(node.id)
  if (!itemId) {
    return null
  }
  const fromData = asObject(node.data)
  const raw = String(node.text ?? fromData?.label ?? '').trim()
  const text = primaryLabelText(raw, readSecondaryLine(node, fromData))
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
