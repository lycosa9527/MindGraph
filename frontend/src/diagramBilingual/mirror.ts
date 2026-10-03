/**
 * Read the one-pass LLM `secondary` object. Saved specs use `textSecondary` instead.
 */

export function readSecondaryMirror(
  spec: Record<string, unknown> | null | undefined
): Record<string, unknown> | null {
  const raw = spec?.secondary
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  return raw as Record<string, unknown>
}

export function mirrorString(
  mirror: Record<string, unknown> | null,
  key: string
): string | undefined {
  if (!mirror) return undefined
  const value = mirror[key]
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

export function mirrorStringList(mirror: Record<string, unknown> | null, key: string): string[] {
  if (!mirror) return []
  const value = mirror[key]
  if (!Array.isArray(value)) return []
  return value.map((item) => (typeof item === 'string' ? item.trim() : ''))
}

export function mirrorRecordList(
  mirror: Record<string, unknown> | null,
  key: string
): Record<string, unknown>[] {
  if (!mirror) return []
  const value = mirror[key]
  if (!Array.isArray(value)) return []
  return value.filter(
    (item): item is Record<string, unknown> =>
      Boolean(item) && typeof item === 'object' && !Array.isArray(item)
  )
}

export function readDiagramLanguages(
  spec: Record<string, unknown> | null | undefined
): { primary: string; secondary: string } | null {
  const raw = spec?.languages
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const record = raw as Record<string, unknown>
  const primary = typeof record.primary === 'string' ? record.primary.trim() : ''
  const secondary = typeof record.secondary === 'string' ? record.secondary.trim() : ''
  if (!primary || !secondary || primary === secondary) return null
  return { primary, secondary }
}

export function specHasSecondaryText(spec: Record<string, unknown> | null | undefined): boolean {
  if (!spec) return false
  const nodes = spec.nodes
  if (Array.isArray(nodes)) {
    for (const node of nodes) {
      if (!node || typeof node !== 'object') continue
      const text = (node as { textSecondary?: unknown }).textSecondary
      if (typeof text === 'string' && text.trim()) return true
    }
  }
  const summaries = spec._mindmap_summaries
  if (Array.isArray(summaries) && summaries.some((summary) => summaryRecordHasGloss(summary))) {
    return true
  }
  return false
}

function summaryRecordHasGloss(summary: unknown): boolean {
  if (!summary || typeof summary !== 'object') return false
  const record = summary as { textSecondary?: unknown; children?: unknown }
  const text = record.textSecondary
  if (typeof text === 'string' && text.trim()) return true
  if (!Array.isArray(record.children)) return false
  return record.children.some((child) => summaryRecordHasGloss(child))
}
