/**
 * Thinking-map node groups follow the active color theme.
 * A solid theme paints every group with that theme. Rainbow uses the
 * mind-map family tokens. A hand-painted color is left in place.
 */
import { getMindMapThemeById, resolveMindMapThemeId } from '@/config/mindMapThemes'
import { MIND_MAP_RAINBOW_TOPIC_COLORS } from '@/config/mindMapVibrantThemes'
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import { isDoubleBubbleTopicId, readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'
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

/** Similarity / difference endpoint of a double-bubble edge (not a topic). */
export function doubleBubbleLeafEndpoint(
  source: PaintNode | undefined,
  target: PaintNode | undefined
): PaintNode | undefined {
  if (source && readDoubleBubbleRole(source)) return source
  if (target && readDoubleBubbleRole(target)) return target
  if (source && !isDoubleBubbleTopicId(source.id)) return source
  if (target && !isDoubleBubbleTopicId(target.id)) return target
  return undefined
}

/** Displayed border on a double-bubble leaf (theme chrome or hand-painted). */
export function doubleBubbleLeafBorderColor(
  themeId: string | null | undefined,
  leaf: PaintNode,
  connections?: Connection[] | null
): string | undefined {
  const paint = thinkingMapDisplayedNodeColors(
    'double_bubble_map',
    themeId,
    leaf,
    leaf.style,
    connections
  )
  return paint?.borderColor ?? leaf.style?.borderColor
}

/**
 * Double-bubble connectors follow the similarity / difference border color.
 * Topic borders do not drive the stroke.
 */
export function doubleBubbleConnectorStroke(
  themeId: string | null | undefined,
  paletteStroke: string | null | undefined,
  source: PaintNode | undefined,
  target: PaintNode | undefined,
  connections?: Connection[] | null
): string {
  const leaf = doubleBubbleLeafEndpoint(source, target)
  if (leaf) {
    const border = doubleBubbleLeafBorderColor(themeId, leaf, connections)
    if (border) {
      return connectorStrokeReadableOnFills(border, [
        handPaintedFill('double_bubble_map', themeId, source, connections),
        handPaintedFill('double_bubble_map', themeId, target, connections),
      ])
    }
  }
  return thinkingMapRenderedConnectorStroke(
    'double_bubble_map',
    themeId,
    paletteStroke,
    source,
    target,
    connections
  )
}

/** Persist connector strokes onto edges that touch painted similarity / difference nodes. */
export function syncDoubleBubbleConnectionsToLeafBorders(
  connections: Connection[],
  nodes: readonly DiagramNode[],
  leafNodeIds: readonly string[],
  borderColor: string
): void {
  if (!borderColor || leafNodeIds.length === 0) return
  const byId = new Map(nodes.map((node) => [node.id, node] as const))
  const leaves = new Set(
    leafNodeIds.filter((id) => {
      const node = byId.get(id)
      return Boolean(node && readDoubleBubbleRole(node))
    })
  )
  if (leaves.size === 0) return
  for (const connection of connections) {
    if (!leaves.has(connection.source) && !leaves.has(connection.target)) continue
    connection.style = { ...(connection.style || {}), strokeColor: borderColor }
  }
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
