import type { StylePresetColors } from '@/config/colorPalette'
import { MIND_MAP_GEOMETRY, mindMapBranchFontSize } from '@/config/mindMapGeometry'
import type { DiagramNode, NodeStyle } from '@/types'

export type MindMapThemeId =
  | 'nordicBlue'
  | 'morandi'
  | 'obsidianDark'
  | 'aurora'
  | 'creative'
  | 'business'

export interface MindMapThemePreset extends StylePresetColors {
  id: MindMapThemeId
  nameKey: string
  previewClass: string
}

/** Curated mind-map color themes (lines + node fills applied via applyStylePreset). */
export const MIND_MAP_THEMES: MindMapThemePreset[] = [
  {
    id: 'nordicBlue',
    nameKey: 'canvas.toolbar.mindMapThemeNordicBlue',
    previewClass: 'bg-sky-100 border-sky-600',
    backgroundColor: '#e8f4f8',
    textColor: '#2c6b7f',
    borderColor: '#5c9ead',
    topicBackgroundColor: '#2c6b7f',
    topicTextColor: '#ffffff',
    topicBorderColor: '#1a4d5c',
  },
  {
    id: 'morandi',
    nameKey: 'canvas.toolbar.mindMapThemeMorandi',
    previewClass: 'bg-stone-100 border-stone-400',
    backgroundColor: '#e7e5e4',
    textColor: '#57534e',
    borderColor: '#a8a29e',
    topicBackgroundColor: '#78716c',
    topicTextColor: '#fafaf9',
    topicBorderColor: '#57534e',
  },
  {
    id: 'obsidianDark',
    nameKey: 'canvas.toolbar.mindMapThemeObsidianDark',
    previewClass: 'bg-gray-800 border-gray-600',
    backgroundColor: '#374151',
    textColor: '#f3f4f6',
    borderColor: '#6b7280',
    topicBackgroundColor: '#111827',
    topicTextColor: '#f9fafb',
    topicBorderColor: '#4b5563',
  },
  {
    id: 'aurora',
    nameKey: 'canvas.toolbar.mindMapThemeAurora',
    previewClass: 'bg-indigo-100 border-violet-600',
    backgroundColor: '#ede9fe',
    textColor: '#312e81',
    borderColor: '#7c3aed',
    topicBackgroundColor: '#4c1d95',
    topicTextColor: '#f5f3ff',
    topicBorderColor: '#312e81',
  },
  {
    id: 'creative',
    nameKey: 'canvas.toolbar.mindMapThemeCreative',
    previewClass: 'bg-purple-50 border-purple-600',
    backgroundColor: '#ede9fe',
    textColor: '#4c1d95',
    borderColor: '#7c3aed',
    topicBackgroundColor: '#7c3aed',
    topicTextColor: '#ffffff',
    topicBorderColor: '#5b21b6',
  },
  {
    id: 'business',
    nameKey: 'canvas.toolbar.mindMapThemeBusiness',
    previewClass: 'bg-emerald-50 border-emerald-600',
    backgroundColor: '#a8e6cf',
    textColor: '#14532d',
    borderColor: '#10b981',
    topicBackgroundColor: '#059669',
    topicTextColor: '#ffffff',
    topicBorderColor: '#047857',
  },
]

export const DEFAULT_MIND_MAP_THEME_ID: MindMapThemeId = 'nordicBlue'

export function getMindMapThemeById(id: MindMapThemeId = DEFAULT_MIND_MAP_THEME_ID): MindMapThemePreset {
  return MIND_MAP_THEMES.find((item) => item.id === id) ?? MIND_MAP_THEMES[0]
}

export function getDefaultMindMapTheme(): MindMapThemePreset {
  return getMindMapThemeById(DEFAULT_MIND_MAP_THEME_ID)
}

export function resolveMindMapThemeId(stored?: string | null): MindMapThemeId {
  if (stored && MIND_MAP_THEMES.some((item) => item.id === stored)) {
    return stored as MindMapThemeId
  }
  return DEFAULT_MIND_MAP_THEME_ID
}

/** Match an applied theme from the central topic colors (before `_mindmap_theme` was persisted). */
export function inferMindMapThemeIdFromNodes(
  nodes: Pick<DiagramNode, 'id' | 'type' | 'style'>[]
): MindMapThemeId | null {
  const topic = nodes.find((n) => n.id === 'topic' && (n.type === 'topic' || n.type === 'center'))
  const topicBorder = topic?.style?.borderColor?.toLowerCase()
  const branchBorder = nodes.find((n) => n.id.startsWith('branch-'))?.style?.borderColor?.toLowerCase()
  for (const theme of MIND_MAP_THEMES) {
    if (topicBorder && theme.topicBorderColor.toLowerCase() === topicBorder) return theme.id
    if (branchBorder && theme.borderColor.toLowerCase() === branchBorder) return theme.id
  }
  return null
}

/** Theme for rendering / new nodes — respects user-applied `_mindmap_theme` on the diagram. */
export function getMindMapThemeForDiagram(
  data?: { _mindmap_theme?: string | null; nodes?: Pick<DiagramNode, 'id' | 'type' | 'style'>[] } | null
): MindMapThemePreset {
  if (data?._mindmap_theme) {
    return getMindMapThemeById(resolveMindMapThemeId(data._mindmap_theme))
  }
  const inferred = data?.nodes ? inferMindMapThemeIdFromNodes(data.nodes) : null
  return getMindMapThemeById(inferred ?? DEFAULT_MIND_MAP_THEME_ID)
}

/** Active theme id for styling new nodes after tree reload (persisted or inferred). */
export function resolveActiveMindMapThemeId(
  data?: { _mindmap_theme?: string | null; nodes?: Pick<DiagramNode, 'id' | 'type' | 'style'>[] } | null
): MindMapThemeId {
  if (data?._mindmap_theme) {
    return resolveMindMapThemeId(data._mindmap_theme)
  }
  const inferred = data?.nodes ? inferMindMapThemeIdFromNodes(data.nodes) : null
  return inferred ?? DEFAULT_MIND_MAP_THEME_ID
}

function isMindMapTopicNode(node: Pick<DiagramNode, 'type'>): boolean {
  return node.type === 'topic' || node.type === 'center'
}

/** Default node colors from a mind-map theme preset (geometry typography included). */
export function mindMapStyleFromTheme(
  node: Pick<DiagramNode, 'type' | 'id'>,
  theme: MindMapThemePreset = getDefaultMindMapTheme()
): Partial<NodeStyle> {
  const useTopic = isMindMapTopicNode(node)
  const fontSize = useTopic
    ? MIND_MAP_GEOMETRY.topicFontSize
    : mindMapBranchFontSize(node.id)
  return {
    backgroundColor: useTopic ? theme.topicBackgroundColor : theme.backgroundColor,
    textColor: useTopic ? theme.topicTextColor : theme.textColor,
    borderColor: useTopic ? theme.topicBorderColor : theme.borderColor,
    fontFamily: MIND_MAP_GEOMETRY.fontFamily,
    fontSize,
    fontWeight: useTopic ? 'bold' : 'normal',
    borderWidth: MIND_MAP_GEOMETRY.borderWidth,
  }
}

export function nodeHasMindMapThemeColors(style?: NodeStyle): boolean {
  return !!(style?.backgroundColor || style?.textColor || style?.borderColor)
}
