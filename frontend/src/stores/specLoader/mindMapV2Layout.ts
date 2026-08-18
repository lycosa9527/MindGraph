/**
 * V2 mind-map side layout — subtree-relative X, sequential root stacking.
 */
import {
  mindMapAdaptiveBranchGap,
  mindMapAdaptiveSiblingGap,
} from '@/config/mindMapAdaptiveGaps'
import {
  getMindMapDiagramStyleById,
  mindMapNodeShapeFromPreset,
} from '@/config/mindMapDiagramStyles'
import { computeSymmetricRootStartYs } from '@/utils/mindMapSideStacking'
import type { Connection, DiagramNode } from '@/types'
import type { NodeShape } from '@/utils/nodeShapeStyle'

import { MINDMAP_LEGACY_ID_DATA_KEY } from '@/utils/mindMapIdentityMigrate'
import { mindMapBranchDataFields } from '@/utils/mindMapLocation'
import {
  ensureMindMapBranchUid,
  MINDMAP_NODE_UID_DATA_KEY,
} from '@/utils/mindMapNodeUid'

import {
  formatMindMapBranchPrefix,
  mindMapClockwiseL1Index,
  type MindMapNumberingGlyphStyle,
  type MindMapNumberingNestedStyle,
} from '@/utils/mindMapBranchNumbering'

import type { MindMapBranchSpec } from './mindMapLegacyLayout'
import {
  estimateNumberedBranchBoxWidth,
  estimateNodeWidthForCanvasMode,
  measureNumberedBranchHeightForCanvasMode,
  measureNumberedUnderlineBoxMetrics,
} from './mindMapMeasurements'

export type MindMapV2LayoutNumbering = {
  enabled: boolean
  prefixStyle: MindMapNumberingGlyphStyle
  nestedStyle: MindMapNumberingNestedStyle
}

function getBranchText(branch: { text?: string; label?: string }): string {
  return (branch.text ?? branch.label ?? '') as string
}

export function layoutMindMapSideV2(
  branches: MindMapBranchSpec[],
  side: 'left' | 'right',
  topicCenterX: number,
  topicCenterY: number,
  topicWidth: number,
  rankSeparation: number,
  nodes: DiagramNode[],
  connections: Connection[],
  startHandleIndex: number,
  _totalBranches: number,
  topicBorderColor: string,
  diagramStyleId?: string | null,
  numbering?: MindMapV2LayoutNumbering | null
): void {
  if (branches.length === 0) return

  const diagramStyle = getMindMapDiagramStyleById(diagramStyleId)

  interface LayoutNode {
    id: string
    text: string
    uid: string
    legacyId?: string
    depth: number
    estimatedWidth: number
    estimatedHeight: number
    children: LayoutNode[]
    branchIndex: number
    shape: NodeShape
  }

  function prefixForParts(parts: number[]): string {
    if (!numbering?.enabled || parts.length === 0) return ''
    return formatMindMapBranchPrefix(parts, numbering.prefixStyle, numbering.nestedStyle)
  }

  function buildTree(
    b: MindMapBranchSpec,
    depth: number,
    branchIndex: number,
    ancestorParts: number[],
    siblingIndex: number
  ): LayoutNode {
    const text = getBranchText(b)
    const uid = ensureMindMapBranchUid(b)
    const id = uid
    const shape = mindMapNodeShapeFromPreset({ id, type: 'branch' }, diagramStyle, depth)
    const parts = [...ancestorParts, siblingIndex]
    const prefix = prefixForParts(parts)
    const estimatedWidth = prefix
      ? estimateNumberedBranchBoxWidth(text, prefix, id, shape)
      : estimateNodeWidthForCanvasMode(text, id, 'v2', shape)
    const estimatedHeight =
      shape === 'underline'
        ? measureNumberedUnderlineBoxMetrics(text, prefix, id).totalHeight
        : measureNumberedBranchHeightForCanvasMode(text, prefix, id, 'v2')
    const children = (b.children ?? []).map((child, childIndex) =>
      buildTree(child, depth + 1, branchIndex, parts, childIndex + 1)
    )
    const legacyId = typeof b.legacyId === 'string' && b.legacyId.trim() ? b.legacyId.trim() : undefined
    return { id, text, uid, legacyId, depth, estimatedWidth, estimatedHeight, children, branchIndex, shape }
  }

  const topLevel = branches.map((b, i) => {
    const branchIndex = side === 'right' ? i : startHandleIndex + i
    const l1Index = mindMapClockwiseL1Index(
      side,
      i,
      side === 'right' ? branches.length : startHandleIndex,
      side === 'left' ? branches.length : 0
    )
    return buildTree(b, 1, branchIndex, [], l1Index)
  })

  function firstLeafShape(node: LayoutNode): NodeShape {
    let cur = node
    while (cur.children.length > 0) {
      const next = cur.children[0]
      if (!next) break
      cur = next
    }
    return cur.shape
  }

  function lastLeafShape(node: LayoutNode): NodeShape {
    let cur = node
    while (cur.children.length > 0) {
      const next = cur.children[cur.children.length - 1]
      if (!next) break
      cur = next
    }
    return cur.shape
  }

  function siblingGapSum(siblings: LayoutNode[]): number {
    let total = 0
    for (let i = 0; i < siblings.length - 1; i++) {
      const upper = siblings[i]
      const lower = siblings[i + 1]
      if (!upper || !lower) continue
      total += mindMapAdaptiveSiblingGap(lastLeafShape(upper), firstLeafShape(lower))
    }
    return total
  }

  function subtreeHeight(node: LayoutNode): number {
    if (node.children.length === 0) return node.estimatedHeight
    const heights = node.children.map((c) => subtreeHeight(c))
    const childrenSpan = heights.reduce((a, b) => a + b, 0) + siblingGapSum(node.children)
    return Math.max(node.estimatedHeight, childrenSpan)
  }

  const yPos = new Map<string, number>()

  function shiftDescendantPositions(node: LayoutNode, delta: number): void {
    for (const child of node.children) {
      const cur = yPos.get(child.id)
      if (cur !== undefined) yPos.set(child.id, cur + delta)
      shiftDescendantPositions(child, delta)
    }
  }

  function assignChildrenY(siblings: LayoutNode[], startY: number): number {
    let y = startY
    siblings.forEach((node, i) => {
      if (i > 0) {
        const prev = siblings[i - 1]
        if (prev) {
          y += mindMapAdaptiveSiblingGap(lastLeafShape(prev), firstLeafShape(node))
        }
      }
      if (node.children.length === 0) {
        yPos.set(node.id, y)
        y += node.estimatedHeight
      } else {
        const childEnd = assignChildrenY(node.children, y)
        const childrenSpan = childEnd - y

        if (childrenSpan >= node.estimatedHeight) {
          const firstChild = node.children[0]
          const lastChild = node.children[node.children.length - 1]
          const childTop = yPos.get(firstChild.id) ?? y
          const childBottom = (yPos.get(lastChild.id) ?? y) + lastChild.estimatedHeight
          const childCenter = (childTop + childBottom) / 2
          yPos.set(node.id, childCenter - node.estimatedHeight / 2)
          y = childEnd
        } else {
          const shift = (node.estimatedHeight - childrenSpan) / 2
          shiftDescendantPositions(node, shift)
          yPos.set(node.id, y)
          y += node.estimatedHeight
        }
      }
    })
    return y
  }

  function layoutSubtreeFromTop(node: LayoutNode, startY: number): number {
    if (node.children.length === 0) {
      yPos.set(node.id, startY)
      return startY + node.estimatedHeight
    }

    const childEnd = assignChildrenY(node.children, startY)
    const childrenSpan = childEnd - startY

    if (childrenSpan >= node.estimatedHeight) {
      const firstChild = node.children[0]
      const lastChild = node.children[node.children.length - 1]
      const childTop = yPos.get(firstChild.id) ?? startY
      const childBottom = (yPos.get(lastChild.id) ?? startY) + lastChild.estimatedHeight
      const childCenter = (childTop + childBottom) / 2
      yPos.set(node.id, childCenter - node.estimatedHeight / 2)
      return childEnd
    }

    const shift = (node.estimatedHeight - childrenSpan) / 2
    shiftDescendantPositions(node, shift)
    yPos.set(node.id, startY)
    return startY + node.estimatedHeight
  }

  const topLevelSpans = topLevel.map((node) => subtreeHeight(node))
  const branchGaps: number[] = []
  for (let i = 0; i < topLevel.length - 1; i++) {
    const upper = topLevel[i]
    const lower = topLevel[i + 1]
    if (!upper || !lower) continue
    branchGaps.push(mindMapAdaptiveBranchGap(lastLeafShape(upper), firstLeafShape(lower)))
  }
  const rootStartYs = computeSymmetricRootStartYs(
    topLevelSpans,
    topicCenterY,
    branchGaps
  )
  topLevel.forEach((node, i) => {
    layoutSubtreeFromTop(node, rootStartYs[i] ?? topicCenterY)
  })

  const topicOuterEdge =
    side === 'right' ? topicCenterX + topicWidth / 2 : topicCenterX - topicWidth / 2

  function createNodes(node: LayoutNode, parentOuterEdge: number): void {
    const y = yPos.get(node.id) ?? 0
    const x =
      side === 'right'
        ? parentOuterEdge + rankSeparation
        : parentOuterEdge - rankSeparation - node.estimatedWidth

    nodes.push({
      id: node.id,
      text: node.text,
      type: 'branch',
      position: { x, y },
      style: { nodeShape: node.shape },
      data: {
        branchIndex: node.branchIndex,
        estimatedWidth: node.estimatedWidth,
        estimatedHeight: node.estimatedHeight,
        [MINDMAP_NODE_UID_DATA_KEY]: node.uid,
        ...(node.legacyId ? { [MINDMAP_LEGACY_ID_DATA_KEY]: node.legacyId } : {}),
        ...mindMapBranchDataFields(side, node.depth),
      },
    })

    const outerEdge = side === 'right' ? x + node.estimatedWidth : x
    node.children.forEach((c) => createNodes(c, outerEdge))
  }
  topLevel.forEach((n) => createNodes(n, topicOuterEdge))

  function createConnections(node: LayoutNode, parentId: string): void {
    if (parentId === 'topic') {
      const sourceHandle = side === 'right' ? 'mindmap-right' : 'mindmap-left'
      const targetHandle = side === 'left' ? 'right-target' : 'left'

      connections.push({
        id: `edge-topic-${node.id}`,
        source: 'topic',
        target: node.id,
        sourceHandle,
        targetHandle,
        style: { strokeColor: topicBorderColor },
      })
    } else {
      const isLeftSide = side === 'left'

      connections.push({
        id: `edge-${parentId}-${node.id}`,
        source: parentId,
        target: node.id,
        sourceHandle: isLeftSide ? 'left-source' : 'right',
        targetHandle: isLeftSide ? 'right-target' : 'left',
        style: { strokeColor: topicBorderColor },
      })
    }
    node.children.forEach((c) => createConnections(c, node.id))
  }
  topLevel.forEach((n) => createConnections(n, 'topic'))
}
