/**
 * Extract GraphicalConcept (_x/_y + phrase) positions from IHMC `.cmap` serialization bytes.
 */
import {
  DEFAULT_CANVAS_HEIGHT,
  DEFAULT_CANVAS_WIDTH,
  DEFAULT_PADDING,
} from '@/composables/diagrams/layoutConfig'
import { normalizeLabel } from '@/utils/cmapLabels'
import {
  type InstanceParsed,
  JavaParseError,
  instanceFieldMap,
  parseJavaSerializationStream,
} from '@/utils/javaSerializationParse'

export type LayoutPositionsByLabel = Record<string, { x: number; y: number }>

function resolveInstance(val: unknown): InstanceParsed | null {
  if (val && typeof val === 'object' && (val as InstanceParsed).kind === 'instance') {
    return val as InstanceParsed
  }
  return null
}

function resolveJavaInt(val: unknown): number | null {
  if (typeof val === 'bigint') {
    const n = Number(val)
    return Number.isFinite(n) ? Math.trunc(n) : null
  }
  if (typeof val === 'number' && Number.isFinite(val)) {
    return Math.trunc(val)
  }
  const inst = resolveInstance(val)
  if (!inst) return null
  const cn = inst.classDesc.name
  if (cn === 'java.lang.Integer' || cn === 'java.lang.Short' || cn === 'java.lang.Byte') {
    const v = inst.values[0]
    if (typeof v === 'number') return Math.trunc(v)
    if (typeof v === 'bigint') {
      const n = Number(v)
      return Number.isFinite(n) ? Math.trunc(n) : null
    }
  }
  return null
}

function phraseFieldToLabel(val: unknown): string | null {
  if (typeof val !== 'string') return null
  const n = normalizeLabel(val)
  return n.length > 0 ? n : null
}

function phraseLabelFromGraphical(inst: InstanceParsed): string | null {
  const map = instanceFieldMap(inst)
  const direct = phraseFieldToLabel(map.get('_phrase'))
  if (direct) return direct
  const entity = map.get('_entity')
  const ent = resolveInstance(entity)
  if (!ent) return null
  const em = instanceFieldMap(ent)
  return phraseFieldToLabel(em.get('_phrase'))
}

function graphicalCoords(map: Map<string, unknown>): { x: number; y: number } | null {
  const x = resolveJavaInt(map.get('_x') ?? map.get('x'))
  const y = resolveJavaInt(map.get('_y') ?? map.get('y'))
  if (x === null || y === null) return null
  return { x, y }
}

function isLayoutGraphicalConcept(inst: InstanceParsed): boolean {
  const n = inst.classDesc.name
  if (!n.includes('GraphicalConcept')) return false
  if (n.includes('GraphicalConceptMap')) return false
  if (n.includes('GraphicalLinkingPhrase')) return false
  return true
}

function fitPositionsToCanvas(raw: LayoutPositionsByLabel): LayoutPositionsByLabel {
  const entries = Object.entries(raw)
  if (entries.length === 0) return raw
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const [, p] of entries) {
    minX = Math.min(minX, p.x)
    minY = Math.min(minY, p.y)
    maxX = Math.max(maxX, p.x)
    maxY = Math.max(maxY, p.y)
  }
  const spanX = Math.max(1, maxX - minX)
  const spanY = Math.max(1, maxY - minY)
  const margin = DEFAULT_PADDING + 48
  const innerW = Math.max(1, DEFAULT_CANVAS_WIDTH - 2 * margin)
  const innerH = Math.max(1, DEFAULT_CANVAS_HEIGHT - 2 * margin)
  const scale = Math.min(innerW / spanX, innerH / spanY)
  const out: LayoutPositionsByLabel = {}
  for (const [label, p] of entries) {
    const nx = margin + (p.x - minX) * scale
    const ny = margin + (p.y - minY) * scale
    out[label] = { x: nx, y: ny }
  }
  return out
}

/**
 * Returns normalized phrase → canvas coordinates (top-left–friendly centers scaled into default canvas).
 * Empty object if parsing fails or no graphical concepts found.
 */
export function extractCmapLayoutPositionsByLabel(cmapBytes: Uint8Array): LayoutPositionsByLabel {
  try {
    const parsed = parseJavaSerializationStream(cmapBytes)
    const raw: LayoutPositionsByLabel = {}
    for (const h of parsed.handles) {
      const inst = resolveInstance(h)
      if (!inst || !isLayoutGraphicalConcept(inst)) continue
      const map = instanceFieldMap(inst)
      const coords = graphicalCoords(map)
      if (!coords) continue
      const { x, y } = coords
      const label = phraseLabelFromGraphical(inst)
      if (!label) continue
      raw[label] = { x, y }
    }
    if (Object.keys(raw).length === 0) return {}
    return fitPositionsToCanvas(raw)
  } catch (err) {
    if (err instanceof JavaParseError) return {}
    throw err
  }
}
