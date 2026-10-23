import {
  isMindMapDiagramType,
  isThinkingMapDiagramType,
} from '@/canvas-ribbon/diagramRibbonCapabilities'
import { collectFormatBrushStyle } from '@/composables/canvasToolbar/formatBrushStyle'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { getMindMapThemeForDiagram, mindMapStyleFromTheme } from '@/config/mindMapThemes'
import type { DiagramData, DiagramNode, DiagramType, NodeStyle } from '@/types'
import {
  solidThemeNodePaint,
  thinkingMapDisplayedNodeColors,
} from '@/utils/thinkingMapNodePaint'

function isTopicLikeNode(node: Pick<DiagramNode, 'type'>): boolean {
  return node.type === 'topic' || node.type === 'center'
}

function paintToNodeStyle(paint: {
  backgroundColor: string
  textColor?: string
  borderColor: string
  borderWidth?: number
  fontSize?: number
  accentBarColor?: string
  accentBarWidth?: number
}): Partial<NodeStyle> {
  const style: Partial<NodeStyle> = {
    backgroundColor: paint.backgroundColor,
    borderColor: paint.borderColor,
  }
  if (paint.textColor) style.textColor = paint.textColor
  if (paint.borderWidth !== undefined) style.borderWidth = paint.borderWidth
  if (paint.fontSize !== undefined) style.fontSize = paint.fontSize
  if (paint.accentBarColor !== undefined) style.accentBarColor = paint.accentBarColor
  if (paint.accentBarWidth !== undefined) style.accentBarWidth = paint.accentBarWidth
  return style
}

function opaqueCssColor(value: string): string | undefined {
  const trimmed = value.trim()
  if (!trimmed || trimmed.toLowerCase() === 'transparent') return undefined
  const match = trimmed.match(
    /^rgba?\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*(?:,\s*([\d.]+)\s*)?\)$/i
  )
  if (match?.[1] !== undefined && Number(match[1]) === 0) return undefined
  return trimmed
}

/** Read visible paint from the canvas when the store has no overrides yet. */
export function renderedFormatBrushColorFallback(nodeId: string): Partial<NodeStyle> | undefined {
  if (typeof document === 'undefined') return undefined
  const escaped =
    typeof CSS !== 'undefined' && typeof CSS.escape === 'function'
      ? CSS.escape(nodeId)
      : nodeId.replace(/\\/g, '\\\\').replace(/"/g, '\\"')
  const host = document.querySelector(`.vue-flow__node[data-id="${escaped}"]`)
  if (!(host instanceof HTMLElement)) return undefined
  const painted = host.querySelector(
    '.circle-node, .bubble-node, .branch-node, .flow-node, .flow-substep-node, .brace-node, .topic-node, .concept-node, .label-node, .mind-map-node, .mind-map-topic-node, .mind-map-legacy-node'
  )
  const el = painted instanceof HTMLElement ? painted : host
  const cs = getComputedStyle(el)
  const backgroundColor = opaqueCssColor(cs.backgroundColor)
  const borderColor = opaqueCssColor(cs.borderTopColor)
  const textColor = opaqueCssColor(cs.color)
  const fontSize = Number.parseFloat(cs.fontSize)
  const weight = Number.parseInt(cs.fontWeight, 10)
  const align =
    cs.textAlign === 'right' || cs.textAlign === 'end'
      ? 'right'
      : cs.textAlign === 'center'
        ? 'center'
        : 'left'
  const line = cs.textDecorationLine || ''
  const textDecoration =
    line.includes('underline') && line.includes('line-through')
      ? 'underline line-through'
      : line.includes('line-through')
        ? 'line-through'
        : line.includes('underline')
          ? 'underline'
          : 'none'
  const fallback: Partial<NodeStyle> = {
    fontFamily: cs.fontFamily,
    fontSize: Number.isFinite(fontSize) ? fontSize : undefined,
    fontWeight: weight >= 600 || cs.fontWeight === 'bold' ? 'bold' : 'normal',
    fontStyle: cs.fontStyle === 'italic' ? 'italic' : 'normal',
    textDecoration,
    textAlign: align,
  }
  if (backgroundColor) fallback.backgroundColor = backgroundColor
  if (borderColor) fallback.borderColor = borderColor
  if (textColor) fallback.textColor = textColor
  return fallback
}

export function resolveFormatBrushThemeFallback(
  diagramType: DiagramType | null | undefined,
  data: DiagramData | null | undefined,
  sourceNode: DiagramNode
): Partial<NodeStyle> | undefined {
  if (!diagramType || !sourceNode) return undefined

  if (isMindMapDiagramType(diagramType)) {
    return mindMapStyleFromTheme(
      sourceNode,
      getMindMapThemeForDiagram(data),
      data?._mindmap_diagram_style,
      data?.connections
    )
  }

  if (diagramType === 'concept_map') {
    const themeId = data?._mindmap_theme
    const paint = solidThemeNodePaint(themeId, isTopicLikeNode(sourceNode))
    if (paint) return paintToNodeStyle(paint)
    const dom = renderedFormatBrushColorFallback(sourceNode.id)
    return dom
  }

  if (isThinkingMapDiagramType(diagramType)) {
    const themeId = data?._mindmap_theme
    const displayed = thinkingMapDisplayedNodeColors(
      diagramType,
      themeId,
      sourceNode,
      sourceNode.style,
      data?.connections
    )
    if (displayed) return paintToNodeStyle(displayed)
    return renderedFormatBrushColorFallback(sourceNode.id)
  }

  return renderedFormatBrushColorFallback(sourceNode.id)
}

export function snapshotFormatBrushStyleForNode(input: {
  diagramType: DiagramType | null | undefined
  data: DiagramData | null | undefined
  sourceNode: DiagramNode
  persistedStyle: NodeStyle | undefined
}): NodeStyle {
  const { diagramType, data, sourceNode, persistedStyle } = input
  const themeFallback = resolveFormatBrushThemeFallback(diagramType, data, sourceNode)
  let copied = collectFormatBrushStyle(sourceNode.style, persistedStyle, themeFallback)
  if (Object.keys(copied).length === 0) {
    const domFallback = renderedFormatBrushColorFallback(sourceNode.id)
    copied = collectFormatBrushStyle(sourceNode.style, persistedStyle, domFallback)
  }

  const isMindMap = isMindMapDiagramType(diagramType)
  if (!copied.nodeShape && isMindMap) {
    copied.nodeShape = resolveMindMapNodeShape(
      {
        id: sourceNode.id,
        type: sourceNode.type,
        style: { ...themeFallback, ...persistedStyle, ...sourceNode.style, ...copied },
      },
      data?._mindmap_diagram_style
    )
  }
  return copied
}
