import type { StylePresetColors } from '@/config/colorPalette'
import { mindMapDiagramStyleUsesLayeredBranchColors } from '@/config/mindMapDiagramStyles'
import { mindMapLayeredBranchColorsForNode, mindMapLayeredCenterTopicColors } from '@/config/mindMapVibrantThemes'
import {
  MIND_MAP_RAINBOW_THEME_ID,
  MIND_MAP_RAINBOW_TOPIC_COLORS,
  mindMapColorsFromVibrantAccent,
} from '@/config/mindMapVibrantThemes'
import { MIND_MAP_GEOMETRY, mindMapBranchFontSize } from '@/config/mindMapGeometry'
import {
  mindMapColorsFromNord,
  NORD,
  nordMindMapSourceNote,
} from '@/config/nordMindMapPresets'
import {
  mindMapColorsFromRadixScale,
  radixMindMapSourceNote,
  RADIX_LIGHT_AMBER,
  RADIX_LIGHT_CRIMSON,
  RADIX_LIGHT_CYAN,
  RADIX_LIGHT_JADE,
  RADIX_LIGHT_MAUVE,
  RADIX_LIGHT_TEAL,
  RADIX_LIGHT_VIOLET,
  RADIX_COLORS_URL,
} from '@/config/radixMindMapPresets'
import type { DiagramNode, NodeStyle } from '@/types'

export type MindMapThemeId =
  | 'vibrantBlue'
  | 'vibrantOrange'
  | 'vibrantYellow'
  | 'vibrantGreen'
  | 'vibrantTeal'
  | 'vibrantRose'
  | 'rainbow'
  | 'nordicBlue'
  | 'nordFrostTeal'
  | 'nordFrostSlate'
  | 'nordAuroraGreen'
  | 'nordAuroraRose'
  | 'nordAuroraGold'
  | 'obsidianDark'
  | 'aurora'
  | 'nordPolarFrost'
  | 'morandi'
  | 'creative'
  | 'business'
  | 'vibrant'
  | 'oceanTeal'
  | 'sunsetBreeze'
  | 'roseWarm'

export interface MindMapThemePreset extends StylePresetColors {
  id: MindMapThemeId
  nameKey: string
  previewClass: string
  /** Verifiable palette reference (URL or Nord scale ids). */
  sourceNote: string
}

const VIBRANT_THEME_SOURCE = `MindGraph classroom palette (Radix-inspired accents — ${RADIX_COLORS_URL})`

const VIBRANT_BLUE: MindMapThemePreset = {
  id: 'vibrantBlue',
  nameKey: 'canvas.toolbar.mindMapThemeVibrantBlue',
  previewClass: 'bg-[#eef2fb] border-[#4A72D4]',
  sourceNote: `${VIBRANT_THEME_SOURCE}; blue accent #4A72D4`,
  ...mindMapColorsFromVibrantAccent('#4A72D4'),
}

const VIBRANT_ORANGE: MindMapThemePreset = {
  id: 'vibrantOrange',
  nameKey: 'canvas.toolbar.mindMapThemeVibrantOrange',
  previewClass: 'bg-[#fef0eb] border-[#FA8055]',
  sourceNote: `${VIBRANT_THEME_SOURCE}; coral accent rgb(250,128,85)`,
  ...mindMapColorsFromVibrantAccent('#FA8055'),
}

const VIBRANT_YELLOW: MindMapThemePreset = {
  id: 'vibrantYellow',
  nameKey: 'canvas.toolbar.mindMapThemeVibrantYellow',
  previewClass: 'bg-[#fff8ef] border-[#FFAD36]',
  sourceNote: `${VIBRANT_THEME_SOURCE}; amber accent rgb(255,173,54)`,
  ...mindMapColorsFromVibrantAccent('#FFAD36'),
}

const VIBRANT_GREEN: MindMapThemePreset = {
  id: 'vibrantGreen',
  nameKey: 'canvas.toolbar.mindMapThemeVibrantGreen',
  previewClass: 'bg-[#f7f9eb] border-[#B5C62A]',
  sourceNote: `${VIBRANT_THEME_SOURCE}; lime accent rgb(181,198,42)`,
  ...mindMapColorsFromVibrantAccent('#B5C62A'),
}

const VIBRANT_TEAL: MindMapThemePreset = {
  id: 'vibrantTeal',
  nameKey: 'canvas.toolbar.mindMapThemeVibrantTeal',
  previewClass: 'bg-[#ebf7fa] border-[#0098B9]',
  sourceNote: `${VIBRANT_THEME_SOURCE}; cyan accent rgb(0,152,185)`,
  ...mindMapColorsFromVibrantAccent('#0098B9'),
}

const VIBRANT_ROSE: MindMapThemePreset = {
  id: 'vibrantRose',
  nameKey: 'canvas.toolbar.mindMapThemeVibrantRose',
  previewClass: 'bg-[#f2f1fa] border-[#7574BC]',
  sourceNote: `${VIBRANT_THEME_SOURCE}; purple accent rgb(117,116,188)`,
  ...mindMapColorsFromVibrantAccent('#7574BC'),
}

/** Rainbow branches — topic neutral; each L1 branch cycles vibrant accents. */
const RAINBOW_THEME: MindMapThemePreset = {
  id: MIND_MAP_RAINBOW_THEME_ID,
  nameKey: 'canvas.toolbar.mindMapThemeRainbow',
  previewClass: 'bg-gradient-to-r from-[#FA8055] via-[#B5C62A] to-[#FF7DC1]',
  sourceNote: `${VIBRANT_THEME_SOURCE}; per-L1 rainbow branch accents`,
  backgroundColor: mindMapColorsFromVibrantAccent('#4A72D4').backgroundColor,
  textColor: mindMapColorsFromVibrantAccent('#4A72D4').textColor,
  borderColor: mindMapColorsFromVibrantAccent('#4A72D4').borderColor,
  topicBackgroundColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
  topicTextColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
  topicBorderColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
}

/**
 * Nord Snow Storm backgrounds with Frost nord8/nord10 accents.
 */
const NORD_THEME_NORDIC_BLUE: MindMapThemePreset = {
  id: 'nordicBlue',
  nameKey: 'canvas.toolbar.mindMapThemeNordicBlue',
  previewClass: 'bg-[#eceff4] border-[#5e81ac]',
  sourceNote: nordMindMapSourceNote('Snow Storm nord6 + Frost nord8/nord10 + Polar Night nord0'),
  ...mindMapColorsFromNord({
    backgroundColor: NORD.snowStorm6,
    textColor: NORD.polarNight0,
    borderColor: NORD.frost8,
    topicBackgroundColor: NORD.frost10,
    topicTextColor: NORD.snowStorm6,
    topicBorderColor: NORD.polarNight3,
  }),
}

/** Nord Frost nord7 teal on Snow Storm — arctic mint accent. */
const NORD_THEME_FROST_TEAL: MindMapThemePreset = {
  id: 'nordFrostTeal',
  nameKey: 'canvas.toolbar.mindMapThemeNordFrostTeal',
  previewClass: 'bg-[#eceff4] border-[#8fbcbb]',
  sourceNote: nordMindMapSourceNote('Snow Storm nord6 + Frost nord7 + Polar Night nord0'),
  ...mindMapColorsFromNord({
    backgroundColor: NORD.snowStorm6,
    textColor: NORD.polarNight0,
    borderColor: NORD.frost7,
    topicBackgroundColor: NORD.frost7,
    topicTextColor: NORD.snowStorm6,
    topicBorderColor: NORD.polarNight3,
  }),
}

/** Nord Frost nord9 slate blue-gray on Snow Storm. */
const NORD_THEME_FROST_SLATE: MindMapThemePreset = {
  id: 'nordFrostSlate',
  nameKey: 'canvas.toolbar.mindMapThemeNordFrostSlate',
  previewClass: 'bg-[#e5e9f0] border-[#81a1c1]',
  sourceNote: nordMindMapSourceNote('Snow Storm nord5 + Frost nord9 + Polar Night nord0'),
  ...mindMapColorsFromNord({
    backgroundColor: NORD.snowStorm5,
    textColor: NORD.polarNight0,
    borderColor: NORD.frost9,
    topicBackgroundColor: NORD.frost9,
    topicTextColor: NORD.snowStorm6,
    topicBorderColor: NORD.frost10,
  }),
}

/** Nord Aurora nord14 green on Snow Storm. */
const NORD_THEME_AURORA_GREEN: MindMapThemePreset = {
  id: 'nordAuroraGreen',
  nameKey: 'canvas.toolbar.mindMapThemeNordAuroraGreen',
  previewClass: 'bg-[#eceff4] border-[#a3be8c]',
  sourceNote: nordMindMapSourceNote('Snow Storm nord6 + Aurora nord14 + Polar Night nord0'),
  ...mindMapColorsFromNord({
    backgroundColor: NORD.snowStorm6,
    textColor: NORD.polarNight0,
    borderColor: NORD.aurora14,
    topicBackgroundColor: NORD.aurora14,
    topicTextColor: NORD.snowStorm6,
    topicBorderColor: NORD.polarNight3,
  }),
}

/** Nord Aurora nord11 rose on Snow Storm. */
const NORD_THEME_AURORA_ROSE: MindMapThemePreset = {
  id: 'nordAuroraRose',
  nameKey: 'canvas.toolbar.mindMapThemeNordAuroraRose',
  previewClass: 'bg-[#e5e9f0] border-[#bf616a]',
  sourceNote: nordMindMapSourceNote('Snow Storm nord5 + Aurora nord11 + Polar Night nord0'),
  ...mindMapColorsFromNord({
    backgroundColor: NORD.snowStorm5,
    textColor: NORD.polarNight0,
    borderColor: NORD.aurora11,
    topicBackgroundColor: NORD.aurora11,
    topicTextColor: NORD.snowStorm6,
    topicBorderColor: NORD.polarNight0,
  }),
}

/** Nord Aurora nord13 gold borders with nord12 ember topic. */
const NORD_THEME_AURORA_GOLD: MindMapThemePreset = {
  id: 'nordAuroraGold',
  nameKey: 'canvas.toolbar.mindMapThemeNordAuroraGold',
  previewClass: 'bg-[#eceff4] border-[#d08770]',
  sourceNote: nordMindMapSourceNote('Snow Storm nord6 + Aurora nord12/nord13 + Polar Night nord0'),
  ...mindMapColorsFromNord({
    backgroundColor: NORD.snowStorm6,
    textColor: NORD.polarNight0,
    borderColor: NORD.aurora13,
    topicBackgroundColor: NORD.aurora12,
    topicTextColor: NORD.snowStorm6,
    topicBorderColor: NORD.polarNight3,
  }),
}

/** Radix Mauve — muted purple-gray, mature alternative to pastel Morandi swatches. */
const RADIX_THEME_MORANDI: MindMapThemePreset = {
  id: 'morandi',
  nameKey: 'canvas.toolbar.mindMapThemeMorandi',
  previewClass: 'bg-[#faf9fb] border-[#8e8c99]',
  sourceNote: radixMindMapSourceNote('Mauve'),
  ...mindMapColorsFromRadixScale(RADIX_LIGHT_MAUVE, { textColor: RADIX_LIGHT_MAUVE.step11 }),
}

/** Nord Polar Night dark UI — Polar Night nord1 background. */
const NORD_THEME_OBSIDIAN: MindMapThemePreset = {
  id: 'obsidianDark',
  nameKey: 'canvas.toolbar.mindMapThemeObsidianDark',
  previewClass: 'bg-[#3b4252] border-[#4c566a]',
  sourceNote: nordMindMapSourceNote('Polar Night nord0–nord3 + Snow Storm nord5/nord6'),
  ...mindMapColorsFromNord({
    backgroundColor: NORD.polarNight1,
    textColor: NORD.snowStorm5,
    borderColor: NORD.polarNight3,
    topicBackgroundColor: NORD.polarNight0,
    topicTextColor: NORD.snowStorm6,
    topicBorderColor: NORD.polarNight2,
  }),
}

/** Nord Aurora nord15 on Polar Night — purple aurora night. */
const NORD_THEME_AURORA: MindMapThemePreset = {
  id: 'aurora',
  nameKey: 'canvas.toolbar.mindMapThemeAurora',
  previewClass: 'bg-[#434c5e] border-[#b48ead]',
  sourceNote: nordMindMapSourceNote('Polar Night nord2 + Aurora nord15 + Frost nord8'),
  ...mindMapColorsFromNord({
    backgroundColor: NORD.polarNight2,
    textColor: NORD.snowStorm4,
    borderColor: NORD.aurora15,
    topicBackgroundColor: NORD.aurora15,
    topicTextColor: NORD.snowStorm6,
    topicBorderColor: NORD.frost8,
  }),
}

/** Nord Polar Night nord2 with Frost nord8 sky topic. */
const NORD_THEME_POLAR_FROST: MindMapThemePreset = {
  id: 'nordPolarFrost',
  nameKey: 'canvas.toolbar.mindMapThemeNordPolarFrost',
  previewClass: 'bg-[#434c5e] border-[#88c0d0]',
  sourceNote: nordMindMapSourceNote('Polar Night nord2 + Frost nord7/nord8 + Snow Storm nord6'),
  ...mindMapColorsFromNord({
    backgroundColor: NORD.polarNight2,
    textColor: NORD.snowStorm4,
    borderColor: NORD.frost7,
    topicBackgroundColor: NORD.frost8,
    topicTextColor: NORD.snowStorm6,
    topicBorderColor: NORD.polarNight3,
  }),
}

function themeFromRadix(
  id: MindMapThemeId,
  nameKey: string,
  previewClass: string,
  scaleName: string,
  colors: StylePresetColors
): MindMapThemePreset {
  return {
    id,
    nameKey,
    previewClass,
    sourceNote: radixMindMapSourceNote(scaleName),
    ...colors,
  }
}

export const MIND_MAP_THEMES: MindMapThemePreset[] = [
  VIBRANT_BLUE,
  VIBRANT_ORANGE,
  VIBRANT_YELLOW,
  VIBRANT_GREEN,
  VIBRANT_TEAL,
  VIBRANT_ROSE,
  RAINBOW_THEME,
  NORD_THEME_NORDIC_BLUE,
  NORD_THEME_FROST_TEAL,
  NORD_THEME_FROST_SLATE,
  NORD_THEME_AURORA_GREEN,
  NORD_THEME_AURORA_ROSE,
  NORD_THEME_AURORA_GOLD,
  NORD_THEME_OBSIDIAN,
  NORD_THEME_AURORA,
  NORD_THEME_POLAR_FROST,
  RADIX_THEME_MORANDI,
  themeFromRadix(
    'creative',
    'canvas.toolbar.mindMapThemeCreative',
    'bg-[#faf8ff] border-[#6e56cf]',
    'Violet',
    mindMapColorsFromRadixScale(RADIX_LIGHT_VIOLET)
  ),
  themeFromRadix(
    'business',
    'canvas.toolbar.mindMapThemeBusiness',
    'bg-[#f4fbf7] border-[#29a383]',
    'Jade',
    mindMapColorsFromRadixScale(RADIX_LIGHT_JADE)
  ),
  themeFromRadix(
    'vibrant',
    'canvas.toolbar.mindMapThemeVibrant',
    'bg-[#fefbe9] border-[#e2a336]',
    'Amber',
    mindMapColorsFromRadixScale(RADIX_LIGHT_AMBER, {
      topicBackgroundColor: RADIX_LIGHT_AMBER.step8,
      topicBorderColor: RADIX_LIGHT_AMBER.step11,
    })
  ),
  themeFromRadix(
    'oceanTeal',
    'canvas.toolbar.mindMapThemeOceanTeal',
    'bg-[#f2fafb] border-[#00a2c7]',
    'Cyan',
    mindMapColorsFromRadixScale(RADIX_LIGHT_CYAN)
  ),
  themeFromRadix(
    'sunsetBreeze',
    'canvas.toolbar.mindMapThemeSunsetBreeze',
    'bg-[#f3fbf9] border-[#12a594]',
    'Teal',
    mindMapColorsFromRadixScale(RADIX_LIGHT_TEAL)
  ),
  themeFromRadix(
    'roseWarm',
    'canvas.toolbar.mindMapThemeRoseWarm',
    'bg-[#fef7f9] border-[#e93d82]',
    'Crimson',
    mindMapColorsFromRadixScale(RADIX_LIGHT_CRIMSON)
  ),
]

export const DEFAULT_MIND_MAP_THEME_ID: MindMapThemeId = 'vibrantBlue'

/** Curated palettes in the appearance picker (vibrant classroom choices). */
export const MIND_MAP_COMMON_THEME_IDS: MindMapThemeId[] = [
  'vibrantBlue',
  'vibrantOrange',
  'vibrantYellow',
  'vibrantGreen',
  'vibrantTeal',
  'vibrantRose',
]

export function getMindMapCommonThemes(): MindMapThemePreset[] {
  return MIND_MAP_COMMON_THEME_IDS.map((id) => getMindMapThemeById(id))
}

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
  theme: MindMapThemePreset = getDefaultMindMapTheme(),
  diagramStyleId?: string | null
): Partial<NodeStyle> {
  const useTopic = isMindMapTopicNode(node)
  const fontSize = useTopic
    ? MIND_MAP_GEOMETRY.topicFontSize
    : mindMapBranchFontSize(node.id)
  const geometry: Partial<NodeStyle> = {
    fontFamily: MIND_MAP_GEOMETRY.fontFamily,
    fontSize,
    fontWeight: useTopic ? 'bold' : 'normal',
    borderWidth: MIND_MAP_GEOMETRY.borderWidth,
  }

  if (useTopic) {
    if (mindMapDiagramStyleUsesLayeredBranchColors(diagramStyleId)) {
      const center = mindMapLayeredCenterTopicColors(theme)
      return {
        ...geometry,
        backgroundColor: center.topicBackgroundColor,
        textColor: center.topicTextColor,
        borderColor: center.topicBorderColor,
      }
    }
    return {
      ...geometry,
      backgroundColor: theme.topicBackgroundColor,
      textColor: theme.topicTextColor,
      borderColor: theme.topicBorderColor,
    }
  }

  if (mindMapDiagramStyleUsesLayeredBranchColors(diagramStyleId)) {
    const layered = mindMapLayeredBranchColorsForNode(node.id, theme.borderColor)
    if (layered) {
      return {
        ...geometry,
        backgroundColor: layered.backgroundColor,
        textColor: layered.textColor,
        borderColor: layered.borderColor,
      }
    }
  }

  return {
    ...geometry,
    backgroundColor: theme.backgroundColor,
    textColor: theme.textColor,
    borderColor: theme.borderColor,
  }
}

export function nodeHasMindMapThemeColors(style?: NodeStyle): boolean {
  return !!(style?.backgroundColor || style?.textColor || style?.borderColor)
}
