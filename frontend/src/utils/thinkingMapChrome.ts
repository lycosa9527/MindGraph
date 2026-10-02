/**
 * Thinking-map chrome aligned to mind map v2 rainbow tokens.
 * Hand-painted colors stay. Empty styles and the old Material defaults
 * resolve to the role paint below.
 */
import { isThinkingMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { LEGACY_MINDMAP_BRANCH_COLORS } from '@/config/mindMapLegacyColors'
import {
  MIND_MAP_RAINBOW_FAMILIES,
  MIND_MAP_RAINBOW_TOPIC_COLORS,
  mindMapRainbowNodeColors,
} from '@/config/mindMapVibrantThemes'
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import { isBraceMapPartNode, readBraceGroupIndex } from '@/utils/braceMapIdentity'
import { isBubbleMapAttributeNode, readBubbleGroupIndex } from '@/utils/bubbleMapIdentity'
import { isCircleMapContextNode, readCircleContextIndex } from '@/utils/circleMapIdentity'
import { readDoubleBubbleIndex, readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'
import { isFlowMapStepNode, isFlowMapSubstepNode, readFlowStepIndex } from '@/utils/flowMapIdentity'
import {
  isMultiFlowCauseNode,
  isMultiFlowEffectNode,
  readMultiFlowIndex,
} from '@/utils/multiFlowMapIdentity'
import { isTreeMapLeafNode, readTreeCategoryIndex } from '@/utils/treeMapIdentity'

export const THINKING_MAP_LEAF_TEXT = '#334155'

const LEGACY_ROLE_FONT_SIZES = new Set([12, 13, 20])

const OLD_TEXT = new Set(['#333333', '#ffffff', '#303133', '#000000', '#606266'])

const OLD_ROLE_PAIRS: ReadonlyArray<readonly [string, string]> = [
  ['#1976d2', '#000000'],
  ['#1976d2', '#0d47a1'],
  ['#1976d2', '#1976d2'],
  ['#e3f2fd', '#1976d2'],
  ['#e3f2fd', '#000000'],
  ['#e3f2fd', '#4e79a7'],
  ['#ffffff', '#409eff'],
  ['#ffffff', '#c8d6e5'],
]

const LEGACY_CONNECTOR_FALLBACKS = new Set([
  '#888',
  '#888888',
  '#bbb',
  '#bbbbbb',
  '#ccc',
  '#cccccc',
  '#3b82f6',
  '#94a3b8',
  '#666',
  '#666666',
  '#64748b',
  '#409eff',
  '#000000',
])

type PaintNode = Pick<DiagramNode, 'id' | 'type' | 'data' | 'style'>

export interface ThinkingMapChrome {
  backgroundColor: string
  textColor: string
  borderColor: string
  borderWidth: number
  fontSize: number
  fontWeight: 'bold' | 'normal'
  boxShadow: string
  accentBarColor?: string
  accentBarWidth?: number
  /** Topic colors stay on the theme; restore clears a stored fill. */
  clearStoredColors: boolean
}

function nonnegative(index: number): number | null {
  return index >= 0 ? index : null
}

function sameColor(left: string | undefined, right: string | undefined): boolean {
  if (!left || !right) return false
  return left.trim().toLowerCase() === right.trim().toLowerCase()
}

/** Group slot whose default fill comes from the rainbow families. */
export function thinkingMapPaletteIndex(
  diagramType: string | null | undefined,
  node: PaintNode
): number | null {
  if (
    !diagramType ||
    node.type === 'topic' ||
    node.type === 'center' ||
    node.type === 'boundary' ||
    node.type === 'label'
  ) {
    return null
  }
  switch (diagramType) {
    case 'bubble_map':
      return isBubbleMapAttributeNode(node) ? nonnegative(readBubbleGroupIndex(node)) : null
    case 'circle_map':
      return isCircleMapContextNode(node) ? nonnegative(readCircleContextIndex(node)) : null
    case 'double_bubble_map': {
      const role = readDoubleBubbleRole(node)
      if (role !== 'leftDiff' && role !== 'rightDiff') return null
      return nonnegative(readDoubleBubbleIndex(node))
    }
    case 'tree_map':
      return nonnegative(readTreeCategoryIndex(node))
    case 'flow_map':
      if (!isFlowMapStepNode(node) && !isFlowMapSubstepNode(node)) return null
      return nonnegative(readFlowStepIndex(node))
    case 'multi_flow_map':
      if (!isMultiFlowCauseNode(node) && !isMultiFlowEffectNode(node)) return null
      return nonnegative(readMultiFlowIndex(node))
    case 'brace_map':
      return isBraceMapPartNode(node) ? nonnegative(readBraceGroupIndex(node)) : null
    default:
      return null
  }
}

export function thinkingMapFamilyLine(groupIndex: number): string {
  const count = MIND_MAP_RAINBOW_FAMILIES.length
  const slot = ((groupIndex % count) + count) % count
  return MIND_MAP_RAINBOW_FAMILIES[slot].line
}

/** L1 fill and line stored on newly loaded nodes. */
export function thinkingMapStampedBranchColor(index: number): { fill: string; border: string } {
  const paint = mindMapRainbowNodeColors(thinkingMapFamilyLine(index), 1)
  return { fill: paint.backgroundColor, border: paint.borderColor }
}

function parentSource(nodeId: string, connections: Connection[] | null | undefined): string | null {
  if (!connections) return null
  const edge = connections.find((item) => item.target === nodeId)
  return edge?.source ?? null
}

function braceIsNested(node: PaintNode, connections: Connection[] | null | undefined): boolean {
  const parent = parentSource(node.id, connections)
  if (!parent) return false
  return parentSource(parent, connections) != null
}

function topicChrome(): ThinkingMapChrome {
  return {
    backgroundColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
    textColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
    borderColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    borderWidth: MIND_MAP_GEOMETRY.borderWidth,
    fontSize: MIND_MAP_GEOMETRY.topicFontSize,
    fontWeight: 'bold',
    boxShadow: MIND_MAP_GEOMETRY.topicShadow,
    clearStoredColors: true,
  }
}

function similarityChrome(): ThinkingMapChrome {
  return {
    backgroundColor: '#FFFFFF',
    textColor: THINKING_MAP_LEAF_TEXT,
    borderColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    borderWidth: MIND_MAP_GEOMETRY.borderWidth,
    fontSize: MIND_MAP_GEOMETRY.branchFontSize,
    fontWeight: 'normal',
    boxShadow: MIND_MAP_GEOMETRY.branchShadow,
    clearStoredColors: false,
  }
}

function groupChrome(index: number, nested: boolean, bar: boolean): ThinkingMapChrome {
  const line = thinkingMapFamilyLine(index)
  if (!nested) {
    const paint = mindMapRainbowNodeColors(line, 1)
    return {
      backgroundColor: paint.backgroundColor,
      textColor: paint.textColor,
      borderColor: paint.borderColor,
      borderWidth: MIND_MAP_GEOMETRY.borderWidth,
      fontSize: MIND_MAP_GEOMETRY.branchFontSize,
      fontWeight: 'normal',
      boxShadow: MIND_MAP_GEOMETRY.branchShadow,
      clearStoredColors: false,
    }
  }
  if (bar) {
    const paint = mindMapRainbowNodeColors(line, 2)
    return {
      backgroundColor: paint.backgroundColor,
      textColor: paint.textColor,
      borderColor: paint.borderColor,
      borderWidth: paint.borderWidth ?? 0,
      fontSize: MIND_MAP_GEOMETRY.fontSize,
      fontWeight: 'normal',
      boxShadow: MIND_MAP_GEOMETRY.branchShadow,
      accentBarColor: paint.accentBarColor,
      accentBarWidth: paint.accentBarWidth,
      clearStoredColors: false,
    }
  }
  const family = MIND_MAP_RAINBOW_FAMILIES.find((item) => item.line === line)
  return {
    backgroundColor: '#FFFFFF',
    textColor: family?.text ?? THINKING_MAP_LEAF_TEXT,
    borderColor: line,
    borderWidth: MIND_MAP_GEOMETRY.borderWidth,
    fontSize: MIND_MAP_GEOMETRY.fontSize,
    fontWeight: 'normal',
    boxShadow: MIND_MAP_GEOMETRY.branchShadow,
    clearStoredColors: false,
  }
}

/** Role paint for a thinking-map node. Null for rings, labels, and bare bridge text. */
export function thinkingMapRoleChrome(
  diagramType: string | null | undefined,
  node: PaintNode,
  connections?: Connection[] | null
): ThinkingMapChrome | null {
  if (!diagramType || !isThinkingMapDiagramType(diagramType)) return null
  if (node.type === 'boundary' || node.type === 'label') return null
  if (node.type === 'topic' || node.type === 'center') return topicChrome()
  if (diagramType === 'double_bubble_map' && readDoubleBubbleRole(node) === 'similarity') {
    return similarityChrome()
  }
  if (diagramType === 'bridge_map') return null
  const index = thinkingMapPaletteIndex(diagramType, node)
  if (index == null) return null
  const nested =
    (diagramType === 'tree_map' && isTreeMapLeafNode(node)) ||
    (diagramType === 'flow_map' && isFlowMapSubstepNode(node)) ||
    (diagramType === 'brace_map' && braceIsNested(node, connections))
  const bar = diagramType === 'tree_map' && isTreeMapLeafNode(node)
  return groupChrome(index, nested, bar)
}

export function isLegacyBranchStamp(fill: string | undefined, border: string | undefined): boolean {
  if (!fill || !border) return false
  return LEGACY_MINDMAP_BRANCH_COLORS.some(
    (color) => sameColor(fill, color.fill) && sameColor(border, color.border)
  )
}

function isRainbowBranchStamp(fill: string | undefined, border: string | undefined): boolean {
  if (!fill || !border) return false
  return MIND_MAP_RAINBOW_FAMILIES.some((family) => {
    const levelOne = sameColor(fill, family.fill) && sameColor(border, family.line)
    const ring = sameColor(fill, '#ffffff') && sameColor(border, family.line)
    return levelOne || ring
  })
}

function isOldRolePair(fill: string | undefined, border: string | undefined): boolean {
  if (!fill || !border) return false
  return OLD_ROLE_PAIRS.some(
    ([oldFill, oldBorder]) => sameColor(fill, oldFill) && sameColor(border, oldBorder)
  )
}

function textIsDefault(text: string | undefined, chromeText: string): boolean {
  if (!text) return true
  if (sameColor(text, chromeText)) return true
  return OLD_TEXT.has(text.trim().toLowerCase())
}

/** True when stored colors are empty or still an old/default stamp. */
export function thinkingMapColorsAreDefault(
  style: NodeStyle | undefined,
  chrome: ThinkingMapChrome
): boolean {
  const fill = style?.backgroundColor
  const border = style?.borderColor
  const text = style?.textColor
  if (!textIsDefault(text, chrome.textColor)) return false
  if (!fill && !border) return true
  if (isLegacyBranchStamp(fill, border) || isRainbowBranchStamp(fill, border)) return true
  if (isOldRolePair(fill, border)) return true
  return (
    sameColor(fill, chrome.backgroundColor) && (!border || sameColor(border, chrome.borderColor))
  )
}

/**
 * Rainbow L2 bars store borderWidth 0. A solid theme does not.
 * Paint width wins, including 0. A stored 0 without paint falls back.
 */
export function thinkingMapBorderWidth(
  paintWidth: number | undefined,
  storedWidth: number | undefined,
  fallback: number
): number {
  if (paintWidth != null) return paintWidth
  if (storedWidth != null && storedWidth > 0) return storedWidth
  return fallback
}

/** Replace old role sizes 12, 13, and 20. Any other stored size is kept. */
export function thinkingMapDisplayedFontSize(stored: unknown, roleSize: number): number {
  const parsed = typeof stored === 'number' ? stored : Number(stored)
  if (!Number.isFinite(parsed) || parsed <= 0) return roleSize
  if (LEGACY_ROLE_FONT_SIZES.has(parsed)) return roleSize
  return parsed
}

export function thinkingMapBoxPadding(oval: boolean): string {
  const horizontal = oval ? MIND_MAP_GEOMETRY.paddingXOval : MIND_MAP_GEOMETRY.paddingX
  return `${MIND_MAP_GEOMETRY.paddingY}px ${horizontal}px`
}

export function rainbowLineForLegacyStroke(color: string | null | undefined): string | null {
  if (!color) return null
  const key = color.trim().toLowerCase()
  const index = LEGACY_MINDMAP_BRANCH_COLORS.findIndex((item) => item.border.toLowerCase() === key)
  if (index < 0) return null
  return thinkingMapFamilyLine(index)
}

export function isLegacyConnectorFallback(color: string | null | undefined): boolean {
  if (!color) return true
  return LEGACY_CONNECTOR_FALLBACKS.has(color.trim().toLowerCase())
}

/**
 * Stroke for a thinking-map edge.
 * Solid themes win. Rainbow maps a Material border onto the matching family line.
 * Old gray fallbacks become the topic border. Any other stored color is kept.
 */
export function diagramEdgeStrokeStyle(
  diagramType: unknown,
  strokeColor: string | undefined,
  strokeWidth: number | undefined,
  legacyFallback: string,
  legacyWidth: number
): { stroke: string; strokeWidth: number; strokeOpacity: number } {
  const type = typeof diagramType === 'string' ? diagramType : undefined
  if (!isThinkingMapDiagramType(type)) {
    return {
      stroke: strokeColor || legacyFallback,
      strokeWidth: strokeWidth || legacyWidth,
      strokeOpacity: 1,
    }
  }
  return {
    stroke: strokeColor || MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
    strokeWidth: strokeWidth || MIND_MAP_GEOMETRY.edgeStrokeWidth,
    strokeOpacity: MIND_MAP_GEOMETRY.edgeStrokeOpacity,
  }
}
