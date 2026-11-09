/**
 * Refresh mind-map text estimates after a label edit.
 * Topic stem width stays on the painted measurement. Branch boxes are the
 * shared wrap measurement, which layout uses instead of a DOM width.
 */
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { diagramPaintFontFamily } from '@/fonts/diagramCanvasFonts'
import type { DiagramData, DiagramNode, NodeStyle } from '@/types'
import { mindMapBranchNumberMapFromData } from '@/utils/mindMapBranchNumbering'
import {
  type MindMapBranchPaintBox,
  createMindMapBranchPaintIndex,
  mindMapBranchPaintBox,
} from '@/utils/mindMapBranchPaintBox'
import { isMindMapLabelMeasureTrusted } from '@/utils/mindMapTextWrap'

import {
  estimateNumberedBranchWidth,
  estimateTopicNodeHeight,
  estimateTopicNodeWidth,
  measureNumberedBranchHeight,
  measureNumberedBranchUnderlineHeight,
} from '../specLoader/mindMap'
import { isLearningSheetBlankDisplayText } from '../specLoader/utils'
import type { DiagramContext } from './types'

function paintedMeasureStyle(
  node: DiagramNode,
  data: DiagramData,
  box: MindMapBranchPaintBox
): NodeStyle {
  const stored = {
    ...(data._node_styles?.[node.id] || {}),
    ...(node.style || {}),
  }
  const storedFamily = typeof stored.fontFamily === 'string' ? stored.fontFamily : undefined
  return {
    ...stored,
    fontSize: box.fontSize,
    // Same stack the branch node paints. A different Latin face makes ASCII
    // quotes wider than the canvas, so that leaf misses the shared edge.
    fontFamily: diagramPaintFontFamily(storedFamily, MIND_MAP_GEOMETRY.fontFamily),
  }
}

function estimatorFontSize(style: NodeStyle): number {
  const custom = style.fontSize
  if (typeof custom === 'number' && Number.isFinite(custom) && custom > 0) return custom
  const parsed = Number.parseFloat(String(custom ?? ''))
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 14
}

/** A failed browser measure must not replace a wrap box the file already has. */
function keepStoredWrapBox(
  node: DiagramNode,
  text: string,
  prefix: string,
  style: NodeStyle
): boolean {
  const stored = node.data?.estimatedWidth
  if (typeof stored !== 'number' || stored <= 0) return false
  const fontSize = estimatorFontSize(style)
  const options = {
    fontWeight: style.fontWeight != null ? String(style.fontWeight) : undefined,
    fontFamily: style.fontFamily,
  }
  if (!isMindMapLabelMeasureTrusted(text, fontSize, options)) return true
  return prefix.length > 0 && !isMindMapLabelMeasureTrusted(prefix, fontSize, options)
}

export function applyMindMapTextEditBox(
  ctx: DiagramContext,
  nodeId: string,
  nodeIndex: number
): void {
  const data = ctx.data.value
  if (!data?.nodes) return
  const currentNode = data.nodes[nodeIndex]
  if (!currentNode) return

  const nodeData = currentNode.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
  const newText = currentNode.text ?? ''
  const diagramData = data as {
    isLearningSheet?: boolean
    is_learning_sheet?: boolean
  }
  const isLearningSheetActive =
    diagramData.isLearningSheet === true || diagramData.is_learning_sheet === true
  const isLearningSheetBlankUpdate =
    isLearningSheetActive &&
    typeof nodeData?.hiddenAnswer === 'string' &&
    nodeData.hiddenAnswer.trim().length > 0 &&
    (nodeData?.hidden === true || isLearningSheetBlankDisplayText(newText))
  if (isLearningSheetBlankUpdate) return

  const box = mindMapBranchPaintBox(
    currentNode,
    data.connections,
    data._mindmap_diagram_style as string | undefined
  )
  const nodeStyle = paintedMeasureStyle(currentNode, data, box)
  const shape = box.shape

  if (nodeId === 'topic') {
    const freshWidth = estimateTopicNodeWidth(newText, nodeStyle)
    const freshHeight = estimateTopicNodeHeight(newText, nodeStyle)
    data.nodes[nodeIndex] = {
      ...currentNode,
      data: {
        ...currentNode.data,
        estimatedWidth: freshWidth,
        estimatedHeight: freshHeight,
      },
    }
    ctx.scheduleMindMapRecalc()
    return
  }

  const numberMap = mindMapBranchNumberMapFromData(data)
  const prefix = numberMap.get(nodeId) ?? ''
  const freshWidth = estimateNumberedBranchWidth(newText, prefix, nodeId, nodeStyle, shape)
  const gloss = (currentNode.textSecondary ?? '').trim()
  const glossExtra = gloss ? Math.ceil(14 * 0.75 * 1.2) : 0
  const freshHeight =
    (shape === 'underline'
      ? measureNumberedBranchUnderlineHeight(newText, prefix, nodeId, nodeStyle)
      : measureNumberedBranchHeight(newText, prefix, nodeId, nodeStyle)) + glossExtra
  data.nodes[nodeIndex] = {
    ...currentNode,
    data: {
      ...currentNode.data,
      estimatedWidth: freshWidth,
      estimatedHeight: freshHeight,
    },
  }
  // Estimate now, so restack does not wait on the editor box. X keeps this
  // wrap box when a later DOM width was measured under a different rule.
  ctx.mindMapNodeHeights.value[nodeId] = freshHeight
  ctx.mindMapNodeWidths.value[nodeId] = freshWidth
  ctx.scheduleMindMapRecalc()
}

function hasStoredWrapBox(node: DiagramNode): boolean {
  const width = node.data?.estimatedWidth
  const height = node.data?.estimatedHeight
  return typeof width === 'number' && width > 0 && typeof height === 'number' && height > 0
}

/**
 * Topic and branch layout boxes from the same wrap the node paints.
 * A saved estimate can still be the old one-line or collapsed width. The load
 * restack replaces that. A later live pass keeps the box it already wrote,
 * because measuring again before the font settles moves only some columns.
 */
export function nodesWithMindMapWrapBoxes(
  nodes: DiagramNode[],
  data: DiagramData,
  options?: { reuseStored?: boolean }
): DiagramNode[] {
  const numberMap = mindMapBranchNumberMapFromData(data)
  const paintOf = createMindMapBranchPaintIndex(
    data.connections,
    data._mindmap_diagram_style as string | undefined
  )
  return nodes.map((node) => {
    if (options?.reuseStored && hasStoredWrapBox(node)) return node
    const box = paintOf(node)
    const nodeStyle = paintedMeasureStyle(node, data, box)
    const shape = box.shape
    if (node.id === 'topic' || node.type === 'topic') {
      return withWrapBox(
        node,
        estimateTopicNodeWidth(node.text ?? '', nodeStyle, shape),
        estimateTopicNodeHeight(node.text ?? '', nodeStyle)
      )
    }
    const text = node.text ?? ''
    const prefix = numberMap.get(node.id) ?? ''
    if (keepStoredWrapBox(node, text, prefix, nodeStyle)) return node
    const width = estimateNumberedBranchWidth(text, prefix, node.id, nodeStyle, shape)
    const gloss = (node.textSecondary ?? '').trim()
    const glossExtra = gloss ? Math.ceil(14 * 0.75 * 1.2) : 0
    const height =
      (shape === 'underline'
        ? measureNumberedBranchUnderlineHeight(text, prefix, node.id, nodeStyle)
        : measureNumberedBranchHeight(text, prefix, node.id, nodeStyle)) + glossExtra
    return withWrapBox(node, width, height)
  })
}

function withWrapBox(node: DiagramNode, width: number, height: number): DiagramNode {
  if (node.data?.estimatedWidth === width && node.data?.estimatedHeight === height) return node
  return {
    ...node,
    data: {
      ...node.data,
      estimatedWidth: width,
      estimatedHeight: height,
    },
  }
}
