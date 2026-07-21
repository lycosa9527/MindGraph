/**
 * V2 mind-map side layout — subtree-relative X, symmetric root stacking.
 */
import {
  DEFAULT_MINDMAP_BRANCH_GAP,
  MINDMAP_SIBLING_GAP,
} from '@/composables/diagrams/layoutConfig'
import {
  getMindMapDiagramStyleById,
  mindMapNodeShapeFromPreset,
} from '@/config/mindMapDiagramStyles'
import { computeSymmetricRootStartYs } from '@/utils/mindMapSideStacking'
import type { Connection, DiagramNode } from '@/types'

import {
  ensureMindMapBranchUid,
  MINDMAP_NODE_UID_DATA_KEY,
} from '@/utils/mindMapNodeUid'

import type { MindMapBranchSpec } from './mindMapLegacyLayout'
import {
  estimateNodeWidthForCanvasMode,
  measureBranchNodeHeightForCanvasMode,
  measureMindMapUnderlineBoxMetrics,
} from './mindMapMeasurements'

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
  diagramStyleId?: string | null
): void {
  if (branches.length === 0) return

  const sideChar = side === 'right' ? 'r' : 'l'
  const diagramStyle = getMindMapDiagramStyleById(diagramStyleId)

  interface LayoutNode {
    id: string
    text: string
    uid: string
    depth: number
    estimatedWidth: number
    estimatedHeight: number
    children: LayoutNode[]
    branchIndex: number
  }

  const globalCounter = { value: 0 }

  function buildTree(b: MindMapBranchSpec, depth: number, branchIndex: number): LayoutNode {
    const idx = globalCounter.value++
    const id = `branch-${sideChar}-${depth}-${idx}`
    const text = getBranchText(b)
    const uid = ensureMindMapBranchUid(b)
    const estimatedWidth = estimateNodeWidthForCanvasMode(text, id, 'v2')
    const shape = mindMapNodeShapeFromPreset(
      { id, type: 'branch' },
      diagramStyle
    )
    const estimatedHeight =
      shape === 'underline'
        ? measureMindMapUnderlineBoxMetrics(text, id).totalHeight
        : measureBranchNodeHeightForCanvasMode(text, id, 'v2')
    const children = (b.children ?? []).map((c) => buildTree(c, depth + 1, branchIndex))
    return { id, text, uid, depth, estimatedWidth, estimatedHeight, children, branchIndex }
  }

  const topLevel = branches.map((b, i) => {
    const branchIndex = side === 'right' ? i : startHandleIndex + i
    return buildTree(b, 1, branchIndex)
  })

  function subtreeHeight(node: LayoutNode): number {
    if (node.children.length === 0) return node.estimatedHeight
    const heights = node.children.map((c) => subtreeHeight(c))
    const childrenSpan =
      heights.reduce((a, b) => a + b, 0) + (node.children.length - 1) * MINDMAP_SIBLING_GAP
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
      if (i > 0) y += MINDMAP_SIBLING_GAP
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

  const crossBranchGap = DEFAULT_MINDMAP_BRANCH_GAP

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

  if (topLevel.length === 2) {
    const rootStartYs = computeSymmetricRootStartYs(topLevelSpans, topicCenterY, crossBranchGap)
    topLevel.forEach((node, i) => {
      layoutSubtreeFromTop(node, rootStartYs[i] ?? topicCenterY)
    })
  } else {
    const totalHeight =
      topLevelSpans.reduce((a, b) => a + b, 0) +
      Math.max(0, topLevel.length - 1) * crossBranchGap
    let y = topicCenterY - totalHeight / 2
    for (let i = 0; i < topLevel.length; i++) {
      y = layoutSubtreeFromTop(topLevel[i], y)
      if (i < topLevel.length - 1) y += crossBranchGap
    }
  }

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
      data: {
        branchIndex: node.branchIndex,
        estimatedWidth: node.estimatedWidth,
        estimatedHeight: node.estimatedHeight,
        [MINDMAP_NODE_UID_DATA_KEY]: node.uid,
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
