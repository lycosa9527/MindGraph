/**
 * Apply streamed label translations onto a cloned diagram spec (no live canvas writes).
 */
import { cloneDiagramSpecJson } from '@/utils/cloneDiagramSpecJson'

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

export function applyDiagramTranslationsToSpec(
  spec: Record<string, unknown>,
  translations: ReadonlyArray<DiagramTranslationPatch>
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
