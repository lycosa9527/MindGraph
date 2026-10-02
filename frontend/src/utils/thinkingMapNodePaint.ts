/**
 * Thinking-map node groups follow the active color theme.
 * A solid theme paints every group with that theme. The default rainbow theme
 * restores the per-group palette. A hand-painted color that is neither the
 * palette nor empty is left in place.
 */
import { getMindMapThemeById, resolveMindMapThemeId } from '@/config/mindMapThemes'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { DiagramNode, NodeStyle } from '@/types'
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
import { thinkingMapSolidThemeStroke } from '@/utils/thinkingMapConnectionStroke'
import { readTreeCategoryIndex } from '@/utils/treeMapIdentity'

export interface ThinkingMapNodePaint {
  backgroundColor: string
  textColor: string
  borderColor: string
}

type PaintNode = Pick<DiagramNode, 'id' | 'type' | 'data' | 'style'>

function nonnegative(index: number): number | null {
  return index >= 0 ? index : null
}

/** Group slot whose default fill comes from the shared branch palette. */
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

function solidThemeNodePaint(
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

/**
 * Theme paint that should win over the stored palette. Null keeps the caller's
 * own color chain (rainbow palette, topic default, or a hand-painted color).
 */
export function thinkingMapDisplayedNodeColors(
  diagramType: string | null | undefined,
  themeId: string | null | undefined,
  node: PaintNode,
  style: NodeStyle | undefined = node.style
): ThinkingMapNodePaint | null {
  const themePaint = solidThemeNodePaint(themeId, isTopicNode(node))
  if (!themePaint) return null
  const backgroundColor = style?.backgroundColor
  const borderColor = style?.borderColor
  const textColor = style?.textColor
  if (!backgroundColor && !borderColor && !textColor) return themePaint
  const index = thinkingMapPaletteIndex(diagramType, node)
  if (index == null || textColor) return null
  const palette = getMindmapBranchColor(index)
  if (backgroundColor === palette.fill && borderColor === palette.border) return themePaint
  return null
}

function stripThemeColors(style: NodeStyle | undefined): NodeStyle | undefined {
  if (!style) return style
  const next: NodeStyle = { ...style }
  delete next.backgroundColor
  delete next.textColor
  delete next.borderColor
  return next
}

/** Put thinking-map nodes back on the default palette after a solid theme. */
export function restoreThinkingMapDefaultNodeColors(
  diagramType: string | null | undefined,
  nodes: DiagramNode[]
): void {
  for (const node of nodes) {
    if (node.type === 'boundary') continue
    const index = thinkingMapPaletteIndex(diagramType, node)
    if (index == null) {
      node.style = stripThemeColors(node.style)
      continue
    }
    const palette = getMindmapBranchColor(index)
    node.style = {
      ...stripThemeColors(node.style),
      backgroundColor: palette.fill,
      borderColor: palette.border,
    }
  }
}
