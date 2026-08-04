/**
 * v2 mind-map vertical gaps from adjacent node shapes.
 * Legacy canvas keeps fixed MINDMAP_SIBLING_GAP / DEFAULT_MINDMAP_BRANCH_GAP.
 */
import {
  DEFAULT_MINDMAP_BRANCH_GAP,
  MINDMAP_MIXED_BRANCH_GAP,
  MINDMAP_MIXED_SIBLING_GAP,
  MINDMAP_SIBLING_GAP,
  MINDMAP_UNDERLINE_BRANCH_GAP,
  MINDMAP_UNDERLINE_SIBLING_GAP,
} from '@/composables/diagrams/layoutConfig'
import type { NodeShape } from '@/utils/nodeShapeStyle'

export function isMindMapBoxShape(shape: NodeShape): boolean {
  return shape !== 'underline'
}

function pairRegime(
  upper: NodeShape,
  lower: NodeShape
): 'underline' | 'mixed' | 'box' {
  const upperLine = !isMindMapBoxShape(upper)
  const lowerLine = !isMindMapBoxShape(lower)
  if (upperLine && lowerLine) return 'underline'
  if (upperLine || lowerLine) return 'mixed'
  return 'box'
}

/** Edge-to-edge gap between consecutive siblings under the same parent. */
export function mindMapAdaptiveSiblingGap(
  upperShape: NodeShape,
  lowerShape: NodeShape
): number {
  switch (pairRegime(upperShape, lowerShape)) {
    case 'underline':
      return MINDMAP_UNDERLINE_SIBLING_GAP
    case 'mixed':
      return MINDMAP_MIXED_SIBLING_GAP
    case 'box':
    default:
      return MINDMAP_SIBLING_GAP
  }
}

/** Edge-to-edge gap between adjacent L1 fans (or top-level packs). */
export function mindMapAdaptiveBranchGap(
  upperShape: NodeShape,
  lowerShape: NodeShape
): number {
  switch (pairRegime(upperShape, lowerShape)) {
    case 'underline':
      return MINDMAP_UNDERLINE_BRANCH_GAP
    case 'mixed':
      return MINDMAP_MIXED_BRANCH_GAP
    case 'box':
    default:
      return DEFAULT_MINDMAP_BRANCH_GAP
  }
}

/** Sum of pairwise gaps between consecutive shapes (length shapes-1). */
export function sumMindMapPairGaps(
  shapes: readonly NodeShape[],
  gapForPair: (upper: NodeShape, lower: NodeShape) => number
): number {
  if (shapes.length < 2) return 0
  let total = 0
  for (let i = 0; i < shapes.length - 1; i++) {
    const upper = shapes[i]
    const lower = shapes[i + 1]
    if (upper == null || lower == null) continue
    total += gapForPair(upper, lower)
  }
  return total
}

/**
 * Normalize pack gap input: a scalar applies between every adjacent span;
 * an array must be length spans-1 (pad/truncate with box branch default).
 */
export function normalizeMindMapPackGaps(
  spanCount: number,
  crossBranchGap: number | readonly number[],
  fallback = DEFAULT_MINDMAP_BRANCH_GAP
): number[] {
  if (spanCount <= 1) return []
  const needed = spanCount - 1
  if (typeof crossBranchGap === 'number') {
    return Array.from({ length: needed }, () => crossBranchGap)
  }
  const out: number[] = []
  for (let i = 0; i < needed; i++) {
    const g = crossBranchGap[i]
    out.push(typeof g === 'number' && Number.isFinite(g) ? g : fallback)
  }
  return out
}
