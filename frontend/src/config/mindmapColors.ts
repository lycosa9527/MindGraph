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
  { fill: '#e3f2fd', border: '#0d47a1' },
  { fill: '#e8f5e9', border: '#1b5e20' },
  { fill: '#fff3e0', border: '#e65100' },
  { fill: '#fce4ec', border: '#880e4f' },
  { fill: '#f3e5f5', border: '#4a148c' },
  { fill: '#e0f7fa', border: '#006064' },
  { fill: '#fff8e1', border: '#f57f17' },
  { fill: '#efebe9', border: '#3e2723' },
  { fill: '#e8eaf6', border: '#283593' },
  { fill: '#f1f8e9', border: '#33691e' },
  { fill: '#fbe9e7', border: '#bf360c' },
  { fill: '#f5f5f5', border: '#212121' },
  { fill: '#e0f2f1', border: '#004d40' },
  { fill: '#fffde7', border: '#f9a825' },
  { fill: '#ede7f6', border: '#4527a0' },
  { fill: '#e1f5fe', border: '#01579b' },
  { fill: '#f8bbd0', border: '#6a1b9a' },
  { fill: '#dcedc8', border: '#1b5e20' },
  { fill: '#cfd8dc', border: '#37474f' },
  { fill: '#ffccbc', border: '#bf360c' },
]

export function getMindmapBranchColor(branchIndex: number): MindmapBranchColor {
  return MINDMAP_BRANCH_COLORS[branchIndex % MINDMAP_BRANCH_COLORS.length]
}
