/**
 * Classic mind-map side layout — column-based X, top-down Y (baseline c2611060e).
 */
import {
  DEFAULT_MINDMAP_BRANCH_GAP,
  DEFAULT_NODE_WIDTH,
  MINDMAP_SIBLING_GAP,
} from '@/composables/diagrams/layoutConfig'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection, DiagramNode } from '@/types'

import {
  estimateNodeWidthForCanvasMode,
  measureBranchNodeHeightForCanvasMode,
} from './mindMapMeasurements'

export interface MindMapBranchSpec {
  text: string
  children?: MindMapBranchSpec[]
}

function getBranchText(branch: { text?: string; label?: string }): string {
  return (branch.text ?? branch.label ?? '') as string
}

export function layoutMindMapSideLegacy(
  branches: MindMapBranchSpec[],
  side: 'left' | 'right',
  topicCenterX: number,
  topicCenterY: number,
  topicWidth: number,
  rankSeparation: number,
  nodes: DiagramNode[],
  connections: Connection[],
  startHandleIndex: number,
  _totalBranches: number
): void {
  if (branches.length === 0) return

  const sideChar = side === 'right' ? 'r' : 'l'

  interface LayoutNode {
    id: string
    text: string
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
    const estimatedWidth = estimateNodeWidthForCanvasMode(text, id, 'legacy')
    const estimatedHeight = measureBranchNodeHeightForCanvasMode(text, id, 'legacy')
    const children = (b.children ?? []).map((c) => buildTree(c, depth + 1, branchIndex))
    return { id, text, depth, estimatedWidth, estimatedHeight, children, branchIndex }
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
  let totalH = 0
  topLevel.forEach((node, i) => {
    totalH += subtreeHeight(node)
    if (i < topLevel.length - 1) totalH += crossBranchGap
  })

  let currentY = topicCenterY - totalH / 2
  topLevel.forEach((node, i) => {
    if (i > 0) currentY += crossBranchGap
    if (node.children.length === 0) {
      yPos.set(node.id, currentY)
      currentY += node.estimatedHeight
    } else {
      const childEnd = assignChildrenY(node.children, currentY)
      const childrenSpan = childEnd - currentY

      if (childrenSpan >= node.estimatedHeight) {
        const firstChild = node.children[0]
        const lastChild = node.children[node.children.length - 1]
        const childTop = yPos.get(firstChild.id) ?? currentY
        const childBottom = (yPos.get(lastChild.id) ?? currentY) + lastChild.estimatedHeight
        const childCenter = (childTop + childBottom) / 2
        yPos.set(node.id, childCenter - node.estimatedHeight / 2)
        currentY = childEnd
      } else {
        const shift = (node.estimatedHeight - childrenSpan) / 2
        shiftDescendantPositions(node, shift)
        yPos.set(node.id, currentY)
        currentY += node.estimatedHeight
      }
    }
  })

  const maxWidths = new Map<number, number>()
  function collectWidths(node: LayoutNode): void {
    maxWidths.set(node.depth, Math.max(maxWidths.get(node.depth) ?? 0, node.estimatedWidth))
    node.children.forEach((c) => collectWidths(c))
  }
  topLevel.forEach((n) => collectWidths(n))

  const columnEdge = new Map<number, number>()
  const depths = Array.from(maxWidths.keys()).sort((a, b) => a - b)

  if (side === 'right') {
    let x = topicCenterX + topicWidth / 2 + rankSeparation
    for (const d of depths) {
      columnEdge.set(d, x)
      x += (maxWidths.get(d) ?? DEFAULT_NODE_WIDTH) + rankSeparation
    }
  } else {
    let x = topicCenterX - topicWidth / 2 - rankSeparation
    for (const d of depths) {
      columnEdge.set(d, x)
      x -= (maxWidths.get(d) ?? DEFAULT_NODE_WIDTH) + rankSeparation
    }
  }

  function createNodes(node: LayoutNode): void {
    const y = yPos.get(node.id) ?? 0
    const edge = columnEdge.get(node.depth) ?? 0
    const x = side === 'right' ? edge : edge - node.estimatedWidth

    nodes.push({
      id: node.id,
      text: node.text,
      type: 'branch',
      position: { x, y },
      data: {
        branchIndex: node.branchIndex,
        estimatedWidth: node.estimatedWidth,
        estimatedHeight: node.estimatedHeight,
      },
    })
    node.children.forEach((c) => createNodes(c))
  }
  topLevel.forEach((n) => createNodes(n))

  let handleIndex = 0
  function createConnections(node: LayoutNode, parentId: string): void {
    if (parentId === 'topic') {
      const handleId =
        side === 'right' ? `mindmap-right-${handleIndex}` : `mindmap-left-${handleIndex}`
      const targetHandle = side === 'left' ? 'right-target' : 'left'
      const strokeColor = getMindmapBranchColor(node.branchIndex, 'legacy').border

      connections.push({
        id: `edge-topic-${node.id}`,
        source: 'topic',
        target: node.id,
        sourceHandle: handleId,
        targetHandle,
        style: { strokeColor },
      })
      handleIndex++
    } else {
      const isLeftSide = side === 'left'
      const strokeColor = getMindmapBranchColor(node.branchIndex, 'legacy').border

      connections.push({
        id: `edge-${parentId}-${node.id}`,
        source: parentId,
        target: node.id,
        sourceHandle: isLeftSide ? 'left-source' : 'right',
        targetHandle: isLeftSide ? 'right-target' : 'left',
        style: { strokeColor },
      })
    }
    node.children.forEach((c) => createConnections(c, node.id))
  }
  topLevel.forEach((n) => createConnections(n, 'topic'))
}
