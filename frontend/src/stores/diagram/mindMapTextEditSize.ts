/**
 * Refresh mind-map text estimates after a label edit.
 * Topic stem width stays on the painted measurement; this only updates the
 * estimate layout will not shrink below.
 */
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { mindMapBranchNumberMapFromData } from '@/utils/mindMapBranchNumbering'

import {
  estimateNumberedBranchWidth,
  estimateTopicNodeHeight,
  estimateTopicNodeWidth,
  measureNumberedBranchHeight,
  measureNumberedBranchUnderlineHeight,
} from '../specLoader/mindMap'
import { isLearningSheetBlankDisplayText } from '../specLoader/utils'
import type { DiagramContext } from './types'

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

  const nodeStyle = {
    ...(data._node_styles?.[nodeId] || {}),
    ...(currentNode.style || {}),
  }

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
  const freshWidth = estimateNumberedBranchWidth(newText, prefix, nodeId, nodeStyle)
  const shape = resolveMindMapNodeShape(
    { id: nodeId, type: currentNode.type ?? 'branch', style: nodeStyle },
    data._mindmap_diagram_style as string | undefined
  )
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
  // Estimate now, so restack does not wait on the editor box. ResizeObserver
  // replaces both with the painted size on the next frame.
  ctx.mindMapNodeHeights.value[nodeId] = freshHeight
  ctx.mindMapNodeWidths.value[nodeId] = freshWidth
  ctx.scheduleMindMapRecalc()
}
