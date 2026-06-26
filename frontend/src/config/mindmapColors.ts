/**
 * Mind-map branch color palette — 12 hues for nodes and connection lines.
 *
 * Radix UI Colors light scales (MIT, https://www.radix-ui.com/colors):
 * step 3 fills on canvas, step 8 borders for readable contrast.
 */
export interface MindmapBranchColor {
  fill: string
  border: string
}

/** Twelve Radix accent scales — one hue per primary branch family. */
export const MINDMAP_BRANCH_COLORS: MindmapBranchColor[] = [
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
  _canvasMode?: string
): MindmapBranchColor {
  return MINDMAP_BRANCH_COLORS[branchIndex % MINDMAP_BRANCH_COLORS.length]
}
