/**
 * Extract GraphicalConcept (_x/_y + phrase) positions from IHMC `.cmap` serialization bytes.
 */
import {
  DEFAULT_CANVAS_HEIGHT,
  DEFAULT_CANVAS_WIDTH,
  DEFAULT_PADDING,
} from '@/composables/diagrams/layoutConfig'
import { pillHalfExtentForOverlap } from '@/composables/diagrams/useRadialLayout'
import {
  type ConceptMapPillFootprintPx,
  estimateConceptMapPillFootprintPx,
} from '@/utils/cmapConceptPillEstimate'
import { extractIhmcStorablePropMap } from '@/utils/cmapGraphExtract'
import { normalizeLabel } from '@/utils/cmapLabels'
import {
  type TopLeftSizedRect,
  countOverlappingRects,
  relaxTopLeftPillLayoutsEstimated,
} from '@/utils/cmapLayoutOverlap'
import {
  type InstanceParsed,
  JavaParseError,
  instanceFieldMap,
  parseJavaSerializationStream,
} from '@/utils/javaSerializationParse'

export type LayoutPositionsByLabel = Record<string, { x: number; y: number }>

/** Optional hints so IHMC anchors scale with MindGraph pill heuristics. */
export interface CmapLayoutFitContext {
  topicLabelNormalized?: string | null
  semanticUnitCount?: number
}

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

function graphicalPropMap(subject: InstanceParsed): Map<string, unknown> {
  const augmented = extractIhmcStorablePropMap(subject)
  if (augmented.size > 0) {
    return augmented
  }
  return instanceFieldMap(subject)
}

function phraseLabelFromGraphical(inst: InstanceParsed): string | null {
  const merged = graphicalPropMap(inst)
  const direct = phraseFieldToLabel(merged.get('_phrase'))
  if (direct) return direct
  const entityPayload = merged.get('_entity')
  const ent = resolveInstance(entityPayload)
  if (!ent) return null
  const nestedMerged = graphicalPropMap(ent)
  const nestedPhrase = nestedMerged.get('_phrase')
  return phraseFieldToLabel(nestedPhrase)
}

function graphicalCoordsForInstance(inst: InstanceParsed): { x: number; y: number } | null {
  return graphicalCoords(graphicalPropMap(inst))
}

function graphicalCoords(map: Map<string, unknown>): { x: number; y: number } | null {
  const x = resolveJavaInt(map.get('_x') ?? map.get('x'))
  const y = resolveJavaInt(map.get('_y') ?? map.get('y'))
  if (x === null || y === null) return null
  return { x, y }
}

function isLayoutGraphicalConcept(inst: InstanceParsed): boolean {
  const n = inst.classDesc.name
  if (n.includes('GraphicalConceptMap')) return false
  if (n.includes('GraphicalConcept') && !n.includes('GraphicalLinkingPhrase')) return true
  if (n.includes('GraphicalLinkingPhrase')) return true
  return false
}

/** Minimum gap between estimated pill rects (pairwise scale + overlap checks). */
const CMAP_LAYOUT_PILL_PAIR_GAP = 20
/** Higher → fewer pairs treated as “mostly horizontal/vertical” for extra separation. */
const AXIAL_DOMINANCE = 1.38
/** Larger reference → gentler `densityPressure` for the same node count. */
const DENSITY_REFERENCE_NODES = 15
const DENSITY_PRESSURE_CAP = 2.4
const SCALE_SEP_CAP_MULT = 80

function footprintForStoredLabel(
  labelKey: string,
  topicNorm: string | null
): ConceptMapPillFootprintPx {
  const role =
    topicNorm !== null &&
    normalizeLabel(topicNorm).length > 0 &&
    normalizeLabel(labelKey) === normalizeLabel(topicNorm)
      ? 'topic'
      : 'branch'
  return estimateConceptMapPillFootprintPx(labelKey, role)
}

function layoutRectsFromPositions(
  layout: LayoutPositionsByLabel,
  footprintByLabel: Record<string, ConceptMapPillFootprintPx>
): TopLeftSizedRect[] {
  return Object.entries(layout).map(([labelKey, p]) => {
    const fp = footprintByLabel[labelKey] ?? footprintForStoredLabel(labelKey, null)
    return {
      key: labelKey,
      x: p.x,
      y: p.y,
      width: Math.max(fp.halfWidth * 2, 44),
      height: Math.max(fp.halfHeight * 2, 36),
    }
  })
}

export function countLayoutOverlapsByFootprints(
  layout: LayoutPositionsByLabel,
  topicNormalized: string | null
): number {
  const labels = Object.keys(layout)
  const footprintByLabel: Record<string, ConceptMapPillFootprintPx> = {}
  labels.forEach((labelKey) => {
    footprintByLabel[labelKey] = footprintForStoredLabel(labelKey, topicNormalized)
  })
  const rects = layoutRectsFromPositions(layout, footprintByLabel)
  return countOverlappingRects(rects, CMAP_LAYOUT_PILL_PAIR_GAP)
}

function fitPositionsToCanvas(
  raw: LayoutPositionsByLabel,
  context?: CmapLayoutFitContext
): LayoutPositionsByLabel {
  const entries = Object.entries(raw)
  if (entries.length === 0) return raw

  const tn = context?.topicLabelNormalized?.trim() ?? ''
  const topicResolved = tn.length > 0 ? normalizeLabel(tn) : null

  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity

  type Row = { label: string; ihmc: { x: number; y: number }; foot: ConceptMapPillFootprintPx }
  const rows: Row[] = []

  for (const [labelStr, ihmc] of entries) {
    const foot = footprintForStoredLabel(labelStr, topicResolved)
    rows.push({ label: labelStr, ihmc, foot })
    minX = Math.min(minX, ihmc.x)
    minY = Math.min(minY, ihmc.y)
    maxX = Math.max(maxX, ihmc.x)
    maxY = Math.max(maxY, ihmc.y)
  }

  const footprintByLabel: Record<string, ConceptMapPillFootprintPx> = {}
  rows.forEach((r) => {
    footprintByLabel[r.label] = r.foot
  })

  const spanX = Math.max(1, maxX - minX)
  const spanY = Math.max(1, maxY - minY)
  const margin = DEFAULT_PADDING + 26
  const innerW = Math.max(1, DEFAULT_CANVAS_WIDTH - 2 * margin)
  const innerH = Math.max(1, DEFAULT_CANVAS_HEIGHT - 2 * margin)
  const scaleToFit = Math.min(innerW / spanX, innerH / spanY)

  const effectiveN =
    typeof context?.semanticUnitCount === 'number' &&
    Number.isFinite(context.semanticUnitCount) &&
    context.semanticUnitCount >= 1
      ? Math.max(context.semanticUnitCount, rows.length)
      : rows.length

  const densityBoost = Math.sqrt(Math.max(effectiveN, 1) / Math.max(DENSITY_REFERENCE_NODES, 1))
  const densityPressure = Math.min(densityBoost, DENSITY_PRESSURE_CAP)

  let separationScale = scaleToFit * densityPressure

  const eps = 1e-6

  for (let i = 0; i < rows.length; i += 1) {
    const ai = rows[i]
    if (!ai) continue
    const radialI = pillHalfExtentForOverlap(ai.foot.halfWidth, ai.foot.halfHeight)

    for (let j = i + 1; j < rows.length; j += 1) {
      const bj = rows[j]
      if (!bj) continue
      const radialJ = pillHalfExtentForOverlap(bj.foot.halfWidth, bj.foot.halfHeight)

      const dxAbs = Math.abs(ai.ihmc.x - bj.ihmc.x)
      const dyAbs = Math.abs(ai.ihmc.y - bj.ihmc.y)
      const dTL = Math.hypot(dxAbs, dyAbs)

      const radialNeed = radialI + radialJ + CMAP_LAYOUT_PILL_PAIR_GAP
      separationScale = Math.max(separationScale, radialNeed / Math.max(dTL, eps))

      const horizontalNeed =
        ai.foot.halfWidth * 2 + bj.foot.halfWidth * 2 + CMAP_LAYOUT_PILL_PAIR_GAP

      const verticalNeed =
        ai.foot.halfHeight * 2 + bj.foot.halfHeight * 2 + CMAP_LAYOUT_PILL_PAIR_GAP

      if (dxAbs >= dyAbs * AXIAL_DOMINANCE) {
        separationScale = Math.max(separationScale, horizontalNeed / Math.max(dxAbs, eps))
      }
      if (dyAbs >= dxAbs * AXIAL_DOMINANCE) {
        separationScale = Math.max(separationScale, verticalNeed / Math.max(dyAbs, eps))
      }
    }
  }

  separationScale = Math.min(separationScale, SCALE_SEP_CAP_MULT * scaleToFit)
  if (!Number.isFinite(separationScale) || separationScale <= 0) separationScale = scaleToFit

  function overlapCountForUniformScale(scl: number): number {
    const temp: LayoutPositionsByLabel = {}
    for (const r of rows) {
      temp[r.label] = {
        x: margin + (r.ihmc.x - minX) * scl,
        y: margin + (r.ihmc.y - minY) * scl,
      }
    }
    return countOverlappingRects(
      layoutRectsFromPositions(temp, footprintByLabel),
      CMAP_LAYOUT_PILL_PAIR_GAP
    )
  }

  const scaleLow = scaleToFit
  const scaleHigh = Math.max(separationScale, scaleLow)
  if (overlapCountForUniformScale(scaleHigh) === 0) {
    if (overlapCountForUniformScale(scaleLow) === 0) {
      separationScale = scaleLow
    } else {
      let lo = scaleLow
      let hi = scaleHigh
      for (let bit = 0; bit < 40; bit += 1) {
        if (hi - lo <= Math.max(1e-6 * hi, 0.025)) {
          break
        }
        const mid = (lo + hi) / 2
        if (overlapCountForUniformScale(mid) === 0) {
          hi = mid
        } else {
          lo = mid
        }
      }
      separationScale = hi
    }
  }

  if (overlapCountForUniformScale(separationScale) === 0) {
    for (let squeeze = 0; squeeze < 16; squeeze += 1) {
      const trial = separationScale * 0.987
      if (trial < scaleToFit * 0.985) {
        break
      }
      if (overlapCountForUniformScale(trial) > 0) {
        break
      }
      separationScale = trial
    }
  }

  const staged: LayoutPositionsByLabel = {}
  const anchors: LayoutPositionsByLabel = {}
  const sizeByLabel: Record<string, { width: number; height: number }> = {}

  rows.forEach((r) => {
    const nx = margin + (r.ihmc.x - minX) * separationScale
    const ny = margin + (r.ihmc.y - minY) * separationScale
    staged[r.label] = { x: nx, y: ny }
    anchors[r.label] = { x: nx, y: ny }
    sizeByLabel[r.label] = {
      width: Math.max(r.foot.halfWidth * 2, 44),
      height: Math.max(r.foot.halfHeight * 2, 36),
    }
  })

  const beforeRelax = countOverlappingRects(
    layoutRectsFromPositions(staged, footprintByLabel),
    CMAP_LAYOUT_PILL_PAIR_GAP
  )
  let out = staged

  if (beforeRelax === 0) {
    return out
  }

  const relaxed = relaxTopLeftPillLayoutsEstimated(
    staged,
    sizeByLabel,
    anchors,
    32,
    CMAP_LAYOUT_PILL_PAIR_GAP,
    0.09
  )

  const afterRelax = countOverlappingRects(
    layoutRectsFromPositions(relaxed, footprintByLabel),
    CMAP_LAYOUT_PILL_PAIR_GAP
  )

  if (afterRelax < beforeRelax) {
    out = relaxed
  }

  return out
}

export function extractCmapLayoutPositionsByLabel(
  cmapBytes: Uint8Array,
  context?: CmapLayoutFitContext
): LayoutPositionsByLabel {
  try {
    const parsed = parseJavaSerializationStream(cmapBytes)
    const raw: LayoutPositionsByLabel = {}
    for (const h of parsed.handles) {
      const inst = resolveInstance(h)
      if (!inst || !isLayoutGraphicalConcept(inst)) continue
      const coords = graphicalCoordsForInstance(inst)
      if (!coords) continue
      const labelText = phraseLabelFromGraphical(inst)
      if (!labelText) continue
      raw[labelText] = { x: coords.x, y: coords.y }
    }
    if (Object.keys(raw).length === 0) return {}
    return fitPositionsToCanvas(raw, context)
  } catch (err) {
    if (err instanceof JavaParseError) return {}
    throw err
  }
}
