/**
 * Thinking-map node groups follow the active color theme.
 * A solid theme paints every group with that theme. Rainbow uses the
 * mind-map family tokens. A hand-painted color is left in place.
 */
import { getMindMapThemeById, resolveMindMapThemeId } from '@/config/mindMapThemes'
import { MIND_MAP_RAINBOW_TOPIC_COLORS } from '@/config/mindMapVibrantThemes'
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import {
  type ThinkingMapChrome,
  thinkingMapColorsAreDefault,
  thinkingMapDisplayedFontSize,
  thinkingMapFillAndBorderAreDefault,
  thinkingMapRoleChrome,
} from '@/utils/thinkingMapChrome'
import {
  connectorStrokeReadableOnFills,
  resolveThinkingMapConnectorStroke,
  thinkingMapSolidThemeStroke,
} from '@/utils/thinkingMapConnectionStroke'

export { thinkingMapPaletteIndex } from '@/utils/thinkingMapChrome'

export interface ThinkingMapNodePaint {
  backgroundColor: string
  /** Omitted when the node stores its own text color. Callers then use that color. */
  textColor?: string
  borderColor: string
  borderWidth?: number
  fontSize?: number
  accentBarColor?: string
  accentBarWidth?: number
}

type PaintNode = Pick<DiagramNode, 'id' | 'type' | 'data' | 'style'>

export function solidThemeNodePaint(
  themeId: string | null | undefined,
  topic: boolean
): ThinkingMapNodePaint | null {
  if (!thinkingMapSolidThemeStroke(themeId)) return null
  const theme = getMindMapThemeById(resolveMindMapThemeId(themeId))
  if (topic) {
    return {
      backgroundColor: theme.topicBackgroundColor,
      textColor: theme.topicTextColor,
      borderColor: theme.topicBorderColor,
    }
  }
  return {
    backgroundColor: theme.backgroundColor,
    textColor: theme.textColor,
    borderColor: theme.borderColor,
  }
}

function isTopicNode(node: PaintNode): boolean {
  return node.type === 'topic' || node.type === 'center'
}

function paintFromChrome(chrome: ThinkingMapChrome): ThinkingMapNodePaint {
  return {
    backgroundColor: chrome.backgroundColor,
    textColor: chrome.textColor,
    borderColor: chrome.borderColor,
    borderWidth: chrome.borderWidth,
    fontSize: chrome.fontSize,
    accentBarColor: chrome.accentBarColor,
    accentBarWidth: chrome.accentBarWidth,
  }
}

/**
 * Role fill and border stay when only the text color was chosen.
 * White similarities and tree leaves do not store a fill; dropping the
 * whole paint would fall through to the parent group color.
 */
function paintKeepingCustomText(
  paint: ThinkingMapNodePaint,
  style: NodeStyle | undefined,
  chrome: ThinkingMapChrome
): ThinkingMapNodePaint | null {
  if (thinkingMapColorsAreDefault(style, chrome)) return paint
  if (!thinkingMapFillAndBorderAreDefault(style, chrome)) return null
  return {
    backgroundColor: paint.backgroundColor,
    borderColor: paint.borderColor,
    borderWidth: paint.borderWidth,
    fontSize: paint.fontSize,
    accentBarColor: paint.accentBarColor,
    accentBarWidth: paint.accentBarWidth,
  }
}

/** Fill the user painted. Theme chrome is omitted so default topic blue stays the connector. */
function handPaintedFill(
  diagramType: string | null | undefined,
  themeId: string | null | undefined,
  node: PaintNode | undefined,
  connections?: Connection[] | null
): string | undefined {
  if (!node) return undefined
  const stored = node.style?.backgroundColor
  if (!stored || stored === 'transparent') return undefined
  const paint = thinkingMapDisplayedNodeColors(diagramType, themeId, node, node.style, connections)
  if (paint) return undefined
  return stored
}

/**
 * Theme connector. A hand-painted fill of that same hue would hide the curve,
 * so the rendered stroke becomes dark ink. The stored connection color stays.
 */
export function thinkingMapRenderedConnectorStroke(
  diagramType: string | null | undefined,
  themeId: string | null | undefined,
  paletteStroke: string | null | undefined,
  source: PaintNode | undefined,
  target: PaintNode | undefined,
  connections?: Connection[] | null
): string {
  const stroke = resolveThinkingMapConnectorStroke(
    themeId,
    paletteStroke,
    MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
  )
  return connectorStrokeReadableOnFills(stroke, [
    handPaintedFill(diagramType, themeId, source, connections),
    handPaintedFill(diagramType, themeId, target, connections),
  ])
}

/**
 * Theme paint that should win over the stored palette. Null keeps the caller's
 * own color chain (a hand-painted fill or border).
 */
export function thinkingMapDisplayedNodeColors(
  diagramType: string | null | undefined,
  themeId: string | null | undefined,
  node: PaintNode,
  style: NodeStyle | undefined = node.style,
  connections?: Connection[] | null
): ThinkingMapNodePaint | null {
  const themePaint = solidThemeNodePaint(themeId, isTopicNode(node))
  if (themePaint) {
    const backgroundColor = style?.backgroundColor
    const borderColor = style?.borderColor
    const textColor = style?.textColor
    if (!backgroundColor && !borderColor && !textColor) return themePaint
    const chrome = thinkingMapRoleChrome(diagramType, node, connections)
    if (!chrome) return null
    return paintKeepingCustomText(themePaint, style, chrome)
  }
  const chrome = thinkingMapRoleChrome(diagramType, node, connections)
  if (!chrome) return null
  return paintKeepingCustomText(paintFromChrome(chrome), style, chrome)
}

function stripThemeColors(style: NodeStyle | undefined): NodeStyle | undefined {
  if (!style) return style
  const next: NodeStyle = { ...style }
  delete next.backgroundColor
  delete next.textColor
  delete next.borderColor
  delete next.accentBarColor
  delete next.accentBarWidth
  return next
}

function withRoleFont(style: NodeStyle | undefined, roleSize: number): NodeStyle | undefined {
  if (!style) return { fontSize: roleSize }
  return {
    ...style,
    fontSize: thinkingMapDisplayedFontSize(style.fontSize, roleSize),
  }
}

/** Put thinking-map nodes back on rainbow chrome after a solid theme. */
export function restoreThinkingMapDefaultNodeColors(
  diagramType: string | null | undefined,
  nodes: DiagramNode[],
  connections?: Connection[] | null
): void {
  for (const node of nodes) {
    if (node.type === 'boundary') continue
    const chrome = thinkingMapRoleChrome(diagramType, node, connections)
    if (!chrome || chrome.clearStoredColors) {
      const roleSize = chrome?.fontSize
      const stripped = stripThemeColors(node.style)
      node.style = roleSize == null ? stripped : withRoleFont(stripped, roleSize)
      continue
    }
    node.style = {
      ...stripThemeColors(node.style),
      backgroundColor: chrome.backgroundColor,
      textColor: chrome.textColor,
      borderColor: chrome.borderColor,
      borderWidth: chrome.borderWidth,
      fontSize: thinkingMapDisplayedFontSize(node.style?.fontSize, chrome.fontSize),
      ...(chrome.accentBarColor
        ? { accentBarColor: chrome.accentBarColor, accentBarWidth: chrome.accentBarWidth }
        : {}),
    }
  }
}
