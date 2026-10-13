/**
 * Apply streamed label translations onto a cloned diagram spec (no live canvas writes).
 * Dual-language diagrams keep `textSecondary`; only the primary line is replaced.
 */
import { cloneDiagramSpecJson } from '@/utils/cloneDiagramSpecJson'
import { parseMindMapSummaryNodeId } from '@/utils/mindMapSummary'

export type DiagramTranslationPatch = {
  itemId: string
  kind: 'node' | 'connection'
  text: string
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

function patchNode(node: Record<string, unknown>, text: string): void {
  node.text = text
  const data = asRecord(node.data)
  if (data) {
    data.label = text
  }
}

function patchSummaryRecord(
  summary: Record<string, unknown>,
  childPath: number[],
  text: string
): void {
  if (childPath.length === 0) {
    summary.text = text
    return
  }
  const children = summary.children
  if (!Array.isArray(children)) {
    return
  }
  const [head, ...rest] = childPath
  const child = asRecord(children[head])
  if (!child) {
    return
  }
  patchSummaryRecord(child, rest, text)
}

function patchMindMapSummaryText(
  spec: Record<string, unknown>,
  nodeId: string,
  text: string
): void {
  const parsed = parseMindMapSummaryNodeId(nodeId)
  if (!parsed) {
    return
  }
  const summaries = spec._mindmap_summaries
  if (!Array.isArray(summaries)) {
    return
  }
  for (const summary of summaries) {
    const rec = asRecord(summary)
    if (!rec || rec.id !== parsed.summaryId) {
      continue
    }
    patchSummaryRecord(rec, parsed.childPath, text)
    return
  }
}

function retargetPrimaryLanguage(spec: Record<string, unknown>, targetLanguage: string): void {
  const languages = asRecord(spec.languages)
  if (!languages) {
    return
  }
  const secondary = typeof languages.secondary === 'string' ? languages.secondary.trim() : ''
  if (!secondary) {
    return
  }
  languages.primary = targetLanguage
}

export function applyDiagramTranslationsToSpec(
  spec: Record<string, unknown>,
  translations: ReadonlyArray<DiagramTranslationPatch>,
  targetLanguage?: string
): Record<string, unknown> {
  const next = cloneDiagramSpecJson(spec)
  const byKey = new Map(translations.map((row) => [`${row.kind}:${row.itemId}`, row.text] as const))
  if (Array.isArray(next.nodes)) {
    for (const node of next.nodes) {
      const rec = asRecord(node)
      if (!rec || typeof rec.id !== 'string') {
        continue
      }
      const text = byKey.get(`node:${rec.id}`)
      if (text != null) {
        patchNode(rec, text)
      }
    }
  }
  for (const row of translations) {
    if (row.kind === 'node') {
      patchMindMapSummaryText(next, row.itemId, row.text)
    }
  }
  if (targetLanguage) {
    retargetPrimaryLanguage(next, targetLanguage)
  }
  if (Array.isArray(next.connections)) {
    for (const conn of next.connections) {
      const rec = asRecord(conn)
      if (!rec || typeof rec.id !== 'string') {
        continue
      }
      const text = byKey.get(`connection:${rec.id}`)
      if (text != null) {
        rec.label = text
      }
    }
  }
  return next
}
