/**
 * Floating-toolbar controls follow the style the node already paints.
 * Thinking-map chrome fills in fields the spec does not store. Labels, the
 * circle ring, bare bridge words, and concept-map pills have their own paint.
 */
import { isMindMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { MIND_MAP_RAINBOW_TOPIC_COLORS } from '@/config/mindMapVibrantThemes'
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import type { BorderStyleType } from '@/utils/borderStyleUtils'
import { colorToHex, parseAlphaFromColor } from '@/utils/colorFormat'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import { type NodeShape, defaultDisplayedNodeShape } from '@/utils/nodeShapeStyle'
import { THINKING_MAP_LEAF_TEXT, thinkingMapRoleChrome } from '@/utils/thinkingMapChrome'
import {
  thinkingMapAdaptiveTextColor,
  thinkingMapStructureColor,
} from '@/utils/thinkingMapConnectionStroke'
import { solidThemeNodePaint, thinkingMapDisplayedNodeColors } from '@/utils/thinkingMapNodePaint'

export interface FloatingToolbarNodeDisplay {
  nodeShape: NodeShape | null
  backgroundColor: string
  backgroundOpacity: number
  textColor: string
  borderColor: string
  borderWidth: number
  borderStyle: BorderStyleType
  fontFamily: string
  fontWeight: 'normal' | 'bold'
  fontStyle: 'normal' | 'italic'
  textDecoration: 'none' | 'underline' | 'line-through' | 'underline line-through'
  textAlign: 'left' | 'center' | 'right'
}

type DisplayNode = Pick<DiagramNode, 'id' | 'type' | 'data' | 'style'>

type LayoutFallback = {
  backgroundColor: string
  textColor: string
  borderColor: string
  fontWeight: 'normal' | 'bold'
  borderWidth: number
}

const CONCEPT_TOPIC_FALLBACK = {
  backgroundColor: '#e3f2fd',
  textColor: '#000000',
  borderColor: '#35506b',
} as const

const CONCEPT_NODE_FALLBACK = {
  backgroundColor: '#e3f2fd',
  textColor: '#333333',
  borderColor: '#4e79a7',
} as const

function isTopicRole(node: DisplayNode): boolean {
  return node.type === 'topic' || node.type === 'center'
}

function isStructureNode(node: DisplayNode): boolean {
  return node.type === 'label' || node.type === 'boundary'
}

export function resolveFloatingToolbarNodeShape(
  diagramType: string | null | undefined,
  node: DisplayNode,
  style: NodeStyle,
  mindmapDiagramStyle?: string | null
): NodeShape | null {
  if (isMindMapDiagramType(diagramType)) {
    return resolveMindMapNodeShape({ id: node.id, type: node.type, style }, mindmapDiagramStyle)
  }
  if (style.nodeShape) return style.nodeShape
  return defaultDisplayedNodeShape(diagramType, node.type)
}

function swatchHex(color: string | undefined, fallback: string): string {
  if (!color) return fallback
  if (color === 'transparent') return color
  return colorToHex(color)
}

function firstColor(...candidates: Array<string | undefined>): string | undefined {
  return candidates.find((color) => Boolean(color))
}

function layoutFallback(
  diagramType: string | null | undefined,
  themeId: string | null | undefined,
  node: DisplayNode,
  style: NodeStyle
): LayoutFallback {
  if (diagramType === 'bridge_map' && !style.nodeShape) {
    return {
      backgroundColor: 'transparent',
      textColor: THINKING_MAP_LEAF_TEXT,
      borderColor: 'transparent',
      fontWeight: 'normal',
      borderWidth: 0,
    }
  }
  if (diagramType === 'concept_map') {
    const topic = isTopicRole(node)
    const painted = solidThemeNodePaint(themeId, topic)
    const fallback = topic ? CONCEPT_TOPIC_FALLBACK : CONCEPT_NODE_FALLBACK
    return {
      backgroundColor: painted?.backgroundColor ?? fallback.backgroundColor,
      textColor: painted?.textColor ?? fallback.textColor,
      borderColor: painted?.borderColor ?? fallback.borderColor,
      fontWeight: topic ? 'bold' : 'normal',
      borderWidth: MIND_MAP_GEOMETRY.borderWidth,
    }
  }
  if (isTopicRole(node)) {
    return {
      backgroundColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
      textColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor,
      borderColor: MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor,
      fontWeight: 'bold',
      borderWidth: MIND_MAP_GEOMETRY.borderWidth,
    }
  }
  return {
    backgroundColor: '#FFFFFF',
    textColor: THINKING_MAP_LEAF_TEXT,
    borderColor: MIND_MAP_GEOMETRY.defaultBorderColor,
    fontWeight: 'normal',
    borderWidth: MIND_MAP_GEOMETRY.borderWidth,
  }
}

function structureDisplay(
  themeId: string | null | undefined,
  node: DisplayNode,
  style: NodeStyle,
  nodeShape: NodeShape | null
): FloatingToolbarNodeDisplay {
  const structure = thinkingMapStructureColor(themeId)
  const bridgeLabel = node.type === 'label' && Boolean(node.data?.isDimensionLabel)
  const ring = node.type === 'boundary'
  const fill = swatchHex(style.backgroundColor, 'transparent')
  return {
    nodeShape,
    backgroundColor: fill,
    backgroundOpacity: parseAlphaFromColor(style.backgroundColor || fill),
    textColor: ring
      ? swatchHex(style.textColor, 'transparent')
      : swatchHex(style.textColor, thinkingMapAdaptiveTextColor(themeId, structure)),
    borderColor: ring
      ? swatchHex(style.borderColor, structure)
      : swatchHex(style.borderColor, 'transparent'),
    borderWidth: style.borderWidth ?? (ring ? MIND_MAP_GEOMETRY.edgeStrokeWidth : 0),
    borderStyle: (style.borderStyle || 'solid') as BorderStyleType,
    fontFamily: style.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontWeight: style.fontWeight || (bridgeLabel ? 'bold' : 'normal'),
    fontStyle: style.fontStyle || (bridgeLabel || ring ? 'normal' : 'italic'),
    textDecoration: style.textDecoration ?? 'none',
    textAlign: style.textAlign ?? (bridgeLabel ? 'right' : 'center'),
  }
}

export function resolveFloatingToolbarNodeDisplay(options: {
  diagramType: string | null | undefined
  themeId?: string | null
  mindmapDiagramStyle?: string | null
  node: DisplayNode
  style: NodeStyle
  connections?: Connection[] | null
}): FloatingToolbarNodeDisplay {
  const { diagramType, themeId, mindmapDiagramStyle, node, style, connections } = options
  const nodeShape = resolveFloatingToolbarNodeShape(diagramType, node, style, mindmapDiagramStyle)
  if (isStructureNode(node)) {
    return structureDisplay(themeId, node, style, nodeShape)
  }

  const chrome = thinkingMapRoleChrome(diagramType, node, connections)
  const paint = thinkingMapDisplayedNodeColors(diagramType, themeId, node, style, connections)
  const fallback = layoutFallback(diagramType, themeId, node, style)
  const rawFill = firstColor(paint?.backgroundColor, style.backgroundColor, chrome?.backgroundColor)

  return {
    nodeShape,
    backgroundColor: swatchHex(rawFill, fallback.backgroundColor),
    backgroundOpacity: parseAlphaFromColor(rawFill || fallback.backgroundColor),
    textColor: swatchHex(
      firstColor(paint?.textColor, style.textColor, chrome?.textColor),
      fallback.textColor
    ),
    borderColor: swatchHex(
      firstColor(paint?.borderColor, style.borderColor, chrome?.borderColor),
      fallback.borderColor
    ),
    borderWidth:
      paint?.borderWidth ?? style.borderWidth ?? chrome?.borderWidth ?? fallback.borderWidth,
    borderStyle: (style.borderStyle || 'solid') as BorderStyleType,
    fontFamily: style.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontWeight: style.fontWeight || chrome?.fontWeight || fallback.fontWeight,
    fontStyle: style.fontStyle || 'normal',
    textDecoration: style.textDecoration ?? 'none',
    textAlign: style.textAlign ?? 'center',
  }
}
