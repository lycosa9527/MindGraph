/**
 * Thinking-map node groups follow the active color theme.
 * A solid theme paints every group with that theme. Rainbow uses the
 * mind-map family tokens. A hand-painted color is left in place.
 */
import { getMindMapThemeById, resolveMindMapThemeId } from '@/config/mindMapThemes'
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import {
  type ThinkingMapChrome,
  thinkingMapColorsAreDefault,
  thinkingMapDisplayedFontSize,
  thinkingMapRoleChrome,
} from '@/utils/thinkingMapChrome'
import { thinkingMapSolidThemeStroke } from '@/utils/thinkingMapConnectionStroke'

export { thinkingMapPaletteIndex } from '@/utils/thinkingMapChrome'

export interface ThinkingMapNodePaint {
  backgroundColor: string
  textColor: string
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
 * Theme paint that should win over the stored palette. Null keeps the caller's
 * own color chain (a hand-painted color).
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
    if (chrome && thinkingMapColorsAreDefault(style, chrome)) return themePaint
    return null
  }
  const chrome = thinkingMapRoleChrome(diagramType, node, connections)
  if (!chrome) return null
  if (!thinkingMapColorsAreDefault(style, chrome)) return null
  return paintFromChrome(chrome)
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
