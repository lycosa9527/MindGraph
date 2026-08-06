/**
 * Shared branch color palettes for thinking maps and mind-map canvases.
 *
 * Default / classic: 20 Material hues (baseline 7c7df0d3) — bubble, flow,
 * double-bubble, tree, brace, circle, multi-flow, and classic mind map.
 *
 * New (v2) mind map node paint uses mindMapThemes; pass canvasMode `'v2'` only
 * when a branch-index caller still needs the Radix-12 scale.
 */
import type { MindMapCanvasMode } from '@/stores/ui'

import { LEGACY_MINDMAP_BRANCH_COLORS } from './mindMapLegacyColors'

export interface MindmapBranchColor {
  fill: string
  border: string
}

/** Material-20 — shared thinking-map / classic mind-map palette (7c7df0d3). */
export const MINDMAP_BRANCH_COLORS: MindmapBranchColor[] = LEGACY_MINDMAP_BRANCH_COLORS

/**
 * Twelve Radix accent scales — explicit v2 mind-map branch-index use only.
 * (MIT, https://www.radix-ui.com/colors — step 3 fills, step 8 borders.)
 */
export const V2_MINDMAP_BRANCH_COLORS: MindmapBranchColor[] = [
  { fill: '#e6f4fe', border: '#5eb1ef' }, // blue
  { fill: '#def7f9', border: '#3db9cf' }, // cyan
  { fill: '#e0f8f3', border: '#53b9ab' }, // teal
  { fill: '#e6f7ed', border: '#56ba9f' }, // jade
  { fill: '#e9f6e9', border: '#65ba74' }, // grass
  { fill: '#fff7c2', border: '#e2a336' }, // amber
  { fill: '#ffefd6', border: '#ec9455' }, // orange
  { fill: '#ffe9f0', border: '#e093b2' }, // crimson
  { fill: '#fee9f5', border: '#dd93c2' }, // pink
  { fill: '#fbebfb', border: '#cf91d8' }, // plum
  { fill: '#f4f0fe', border: '#aa99ec' }, // violet
  { fill: '#edf2fe', border: '#8da4ef' }, // indigo
]

export function getMindmapBranchColor(
  branchIndex: number,
  canvasMode?: MindMapCanvasMode
): MindmapBranchColor {
  // Default and classic (`'legacy'`) share Material-20; only explicit v2 differs.
  if (canvasMode === 'v2') {
    return V2_MINDMAP_BRANCH_COLORS[branchIndex % V2_MINDMAP_BRANCH_COLORS.length]
  }
  return MINDMAP_BRANCH_COLORS[branchIndex % MINDMAP_BRANCH_COLORS.length]
}
