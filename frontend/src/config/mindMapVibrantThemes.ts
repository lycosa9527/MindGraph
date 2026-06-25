import type { StylePresetColors } from '@/config/colorPalette'
import { mindMapBranchDepth, sortMindMapTopicChildIds } from '@/config/mindMapGeometry'
import type { Connection, DiagramNode } from '@/types'

/** Theme picker blue — unchanged. */
export const MIND_MAP_VIBRANT_BLUE = '#4A72D4'

/** Six solid theme swatches (appearance picker). */
export const MIND_MAP_THEME_ACCENTS = [
  MIND_MAP_VIBRANT_BLUE,
  '#FA8055', // rgb(250, 128, 85)
  '#FFAD36', // rgb(255, 173, 54)
  '#B5C62A', // rgb(181, 198, 42)
  '#0098B9', // rgb(0, 152, 185)
  '#7574BC', // rgb(117, 116, 188)
] as const

/** Rainbow branch cycle — coral → orange → lime → cyan → blue → purple → pink. */
export const MIND_MAP_RAINBOW_ACCENTS = [
  '#FA8055',
  '#FFAD36',
  '#B5C62A',
  '#0098B9',
  MIND_MAP_VIBRANT_BLUE,
  '#7574BC',
  '#FF7DC1', // rgb(255, 125, 193)
] as const

/** @deprecated Use MIND_MAP_THEME_ACCENTS or MIND_MAP_RAINBOW_ACCENTS. */
export const MIND_MAP_VIBRANT_ACCENTS = MIND_MAP_RAINBOW_ACCENTS

export const MIND_MAP_RAINBOW_THEME_ID = 'rainbow' as const

export const MIND_MAP_RAINBOW_TOPIC_COLORS: Pick<
  StylePresetColors,
  'topicBackgroundColor' | 'topicTextColor' | 'topicBorderColor'
> = {
  topicBackgroundColor: '#3d4a6e',
  topicTextColor: '#ffffff',
  topicBorderColor: '#2c3654',
}

export interface RainbowBranchNodeColors {
  backgroundColor: string
  textColor: string
  borderColor: string
}

function parseHex(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ]
}

function toHex(r: number, g: number, b: number): string {
  const clamp = (n: number) => Math.max(0, Math.min(255, Math.round(n)))
  return `#${[clamp(r), clamp(g), clamp(b)]
    .map((n) => n.toString(16).padStart(2, '0'))
    .join('')}`
}

function mixHex(a: string, b: string, weight: number): string {
  const [ar, ag, ab] = parseHex(a)
  const [br, bg, bb] = parseHex(b)
  const w = Math.max(0, Math.min(1, weight))
  return toHex(ar + (br - ar) * w, ag + (bg - ag) * w, ab + (bb - ab) * w)
}

function relativeLuminance(hex: string): number {
  const [r, g, b] = parseHex(hex).map((c) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function topicTextOnAccent(accent: string): string {
  return relativeLuminance(accent) > 0.58 ? '#422006' : '#ffffff'
}

/** Build a full mind-map palette from one saturated accent (solid theme swatches). */
export function mindMapColorsFromVibrantAccent(accent: string): StylePresetColors {
  return {
    backgroundColor: mixHex(accent, '#ffffff', 0.88),
    textColor: mixHex(accent, '#1e293b', 0.72),
    borderColor: accent,
    topicBackgroundColor: accent,
    topicTextColor: topicTextOnAccent(accent),
    topicBorderColor: mixHex(accent, '#0f172a', 0.22),
  }
}

/**
 * Rainbow branch node colors by depth (reference: L1 solid fill + white text,
 * L2/L3+ progressively lighter tints with accent-hued text).
 */
export function mindMapRainbowNodeColors(
  accent: string,
  depth: number
): RainbowBranchNodeColors {
  if (depth <= 1) {
    return {
      backgroundColor: accent,
      textColor: '#ffffff',
      borderColor: mixHex(accent, '#000000', 0.14),
    }
  }
  if (depth === 2) {
    return {
      backgroundColor: mixHex(accent, '#ffffff', 0.76),
      textColor: mixHex(accent, '#1e293b', 0.42),
      borderColor: mixHex(accent, '#ffffff', 0.38),
    }
  }
  return {
    backgroundColor: mixHex(accent, '#ffffff', 0.87),
    textColor: mixHex(accent, '#0f172a', 0.52),
    borderColor: mixHex(accent, '#ffffff', 0.48),
  }
}

export function isRainbowMindMapTheme(themeId?: string | null): boolean {
  return themeId === MIND_MAP_RAINBOW_THEME_ID
}

function isTopicNode(node: Pick<DiagramNode, 'type'>): boolean {
  return node.type === 'topic' || node.type === 'center'
}

export function findMindMapL1RootId(nodeId: string, connections: Connection[]): string | null {
  if (nodeId === 'topic') return null
  const parentMap = new Map<string, string>()
  connections.forEach((c) => parentMap.set(c.target, c.source))
  let current: string | undefined = nodeId
  while (current) {
    const parent = parentMap.get(current)
    if (!parent) return null
    if (parent === 'topic') return current
    current = parent
  }
  return null
}

export function getMindMapL1BranchIds(connections: Connection[]): string[] {
  return sortMindMapTopicChildIds(
    connections.filter((c) => c.source === 'topic').map((c) => c.target)
  )
}

export function getMindMapL1BranchIndex(l1Id: string, connections: Connection[]): number {
  const idx = getMindMapL1BranchIds(connections).indexOf(l1Id)
  return idx >= 0 ? idx : 0
}

export function rainbowAccentForL1Index(index: number): string {
  return MIND_MAP_RAINBOW_ACCENTS[index % MIND_MAP_RAINBOW_ACCENTS.length]
}

export function rainbowAccentForNode(nodeId: string, connections: Connection[]): string | null {
  const l1Root = findMindMapL1RootId(nodeId, connections)
  if (!l1Root) return null
  return rainbowAccentForL1Index(getMindMapL1BranchIndex(l1Root, connections))
}

export function mindMapRainbowColorsForNode(
  nodeId: string,
  connections: Connection[]
): RainbowBranchNodeColors | null {
  const accent = rainbowAccentForNode(nodeId, connections)
  if (!accent) return null
  return mindMapRainbowNodeColors(accent, mindMapBranchDepth(nodeId))
}

/** Depth-layered branch colors for solid themes (formal / soft diagram styles). */
export function mindMapLayeredBranchColorsFromAccent(
  accent: string,
  depth: number
): RainbowBranchNodeColors {
  return mindMapRainbowNodeColors(accent, depth)
}

/** Center topic for layered diagram styles — darker than L1 accent fill. */
export function mindMapLayeredCenterTopicColors(
  theme: Pick<StylePresetColors, 'topicBorderColor'>
): Pick<StylePresetColors, 'topicBackgroundColor' | 'topicTextColor' | 'topicBorderColor'> {
  const centerBg = theme.topicBorderColor
  return {
    topicBackgroundColor: centerBg,
    topicTextColor: '#ffffff',
    topicBorderColor: mixHex(centerBg, '#0f172a', 0.22),
  }
}

export function mindMapLayeredBranchColorsForNode(
  nodeId: string,
  accent: string
): RainbowBranchNodeColors | null {
  if (!nodeId.startsWith('branch-')) return null
  return mindMapLayeredBranchColorsFromAccent(accent, mindMapBranchDepth(nodeId))
}

/** Flat branch palette (legacy helper — non-rainbow themes). */
export function mindMapBranchColorsForL1Index(index: number): StylePresetColors {
  return mindMapColorsFromVibrantAccent(MIND_MAP_THEME_ACCENTS[index % MIND_MAP_THEME_ACCENTS.length])
}

export function mindMapBranchColorsForNode(
  nodeId: string,
  connections: Connection[]
): StylePresetColors | null {
  const l1Root = findMindMapL1RootId(nodeId, connections)
  if (!l1Root) return null
  return mindMapBranchColorsForL1Index(getMindMapL1BranchIndex(l1Root, connections))
}

export function syncRainbowMindMapConnectionColors(
  connections: Connection[],
  nodes?: DiagramNode[]
): void {
  const topicBorder =
    nodes?.find((n) => n.id === 'topic')?.style?.borderColor ??
    MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor

  connections.forEach((conn) => {
    const branchId = conn.source === 'topic' ? conn.target : conn.target
    const accent = rainbowAccentForNode(branchId, connections)
    const strokeColor = accent ?? topicBorder
    conn.style = { ...(conn.style || {}), strokeColor }
  })
}

/** Apply per-L1 rainbow families with depth-based fills; topic stays dark navy. */
export function applyRainbowMindMapColors(
  nodes: DiagramNode[],
  connections: Connection[]
): void {
  nodes.forEach((node) => {
    if (node.type === 'boundary') return

    if (isTopicNode(node)) {
      node.style = {
        ...(node.style || {}),
        backgroundColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
        textColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
        borderColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
      }
      return
    }

    const colors = mindMapRainbowColorsForNode(node.id, connections)
    if (!colors) return

    node.style = {
      ...(node.style || {}),
      backgroundColor: colors.backgroundColor,
      textColor: colors.textColor,
      borderColor: colors.borderColor,
    }
  })

  syncRainbowMindMapConnectionColors(connections, nodes)
}
