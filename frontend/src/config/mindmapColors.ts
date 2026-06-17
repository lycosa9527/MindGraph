/**
 * Mindmap branch color palette - 20 colors for nodes and connection lines.
 * Each entry: light fill for node background, darker same-hue border for visibility.
 * Borders are 1–2 shades darker than fill for clear contrast (e.g. light blue → dark blue).
 */
export interface MindmapBranchColor {
  fill: string
  border: string
}

export const MINDMAP_BRANCH_COLORS: MindmapBranchColor[] = [
  { fill: '#eff6ff', border: '#93c5fd' },
  { fill: '#ecfdf5', border: '#6ee7b7' },
  { fill: '#fff7ed', border: '#fdba74' },
  { fill: '#fdf2f8', border: '#f9a8d4' },
  { fill: '#f5f3ff', border: '#c4b5fd' },
  { fill: '#ecfeff', border: '#67e8f9' },
  { fill: '#fefce8', border: '#fde047' },
  { fill: '#fafaf9', border: '#CBD5E1' },
  { fill: '#eef2ff', border: '#a5b4fc' },
  { fill: '#f0fdf4', border: '#86efac' },
  { fill: '#fff1f2', border: '#fda4af' },
  { fill: '#ffffff', border: '#CBD5E1' },
  { fill: '#f0fdfa', border: '#5eead4' },
  { fill: '#fef9c3', border: '#facc15' },
  { fill: '#faf5ff', border: '#d8b4fe' },
  { fill: '#f0f9ff', border: '#7dd3fc' },
  { fill: '#fce7f3', border: '#f0abfc' },
  { fill: '#f7fee7', border: '#bef264' },
  { fill: '#f8fafc', border: '#CBD5E1' },
  { fill: '#fff7ed', border: '#fdba74' },
]

export function getMindmapBranchColor(branchIndex: number): MindmapBranchColor {
  return MINDMAP_BRANCH_COLORS[branchIndex % MINDMAP_BRANCH_COLORS.length]
}
