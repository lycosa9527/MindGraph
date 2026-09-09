/**
 * Place v2 summary (概要) nodes after the main mind-map tree layout.
 */
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { getMindMapThemeForDiagram } from '@/config/mindMapThemes'
import type {
  Connection,
  DiagramData,
  DiagramNode,
  MindMapSummaryChildSpec,
  MindMapSummarySpec,
} from '@/types'
import { mindMapLocationPathKey } from '@/utils/mindMapLocation'
import {
  filterTreeMindMapNodes,
  isMindMapSummaryNode,
  mindMapSummaryChildNodeId,
  mindMapSummaryRootNodeId,
  readMindMapSummaries,
  siblingPathsSharingParent,
} from '@/utils/mindMapSummary'
import { MINDMAP_SUMMARY_TIP_NODE_GAP, mindMapSummaryBracePath } from '@/utils/mindMapSummaryBrace'

export const MINDMAP_SUMMARY_BRACE_GAP = 16
export const MINDMAP_SUMMARY_CHILD_GAP_X = 36
export const MINDMAP_SUMMARY_CHILD_GAP_Y = 10

type SizedBox = { x: number; y: number; width: number; height: number }

function nodeBox(
  node: DiagramNode,
  widths: Record<string, number>,
  heights: Record<string, number>
): SizedBox | null {
  const x = node.position?.x
  const y = node.position?.y
  if (x == null || y == null) return null
  const width = widths[node.id] ?? node.style?.width ?? MIND_MAP_GEOMETRY.minWidth
  const height = heights[node.id] ?? node.style?.height ?? MIND_MAP_GEOMETRY.minHeight
  return { x, y, width, height }
}

function unionBoxes(boxes: SizedBox[]): SizedBox | null {
  if (boxes.length === 0) return null
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const box of boxes) {
    minX = Math.min(minX, box.x)
    minY = Math.min(minY, box.y)
    maxX = Math.max(maxX, box.x + box.width)
    maxY = Math.max(maxY, box.y + box.height)
  }
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY }
}

function summaryStyle(data: DiagramData | null | undefined): DiagramNode['style'] {
  const theme = getMindMapThemeForDiagram(data as { _mindmap_theme?: string | null } | null)
  return {
    backgroundColor: theme.topicBackgroundColor,
    borderColor: theme.borderColor,
    textColor: theme.topicTextColor,
    nodeShape: 'rounded',
    borderWidth: MIND_MAP_GEOMETRY.borderWidth,
  }
}

function makeSummaryNode(
  id: string,
  text: string,
  x: number,
  y: number,
  style: DiagramNode['style'],
  extraData: Record<string, unknown>
): DiagramNode {
  return {
    id,
    text,
    type: 'summary',
    position: { x, y },
    style,
    data: {
      label: text,
      ...extraData,
    },
  }
}

function coveredSide(coveredPaths: readonly string[]): 'left' | 'right' {
  const first = coveredPaths[0] ?? 'r/0'
  return first.startsWith('l/') ? 'left' : 'right'
}

function placeChildColumn(
  summaryId: string,
  children: readonly MindMapSummaryChildSpec[] | undefined,
  originX: number,
  originY: number,
  outward: 1 | -1,
  style: DiagramNode['style'],
  widths: Record<string, number>,
  heights: Record<string, number>,
  prefix: number[]
): DiagramNode[] {
  if (!children || children.length === 0) return []
  const nodes: DiagramNode[] = []
  const boxes: { height: number; width: number }[] = []
  for (const [index] of children.entries()) {
    const id = mindMapSummaryChildNodeId(summaryId, [...prefix, index])
    boxes.push({
      width: widths[id] ?? MIND_MAP_GEOMETRY.minWidth,
      height: heights[id] ?? MIND_MAP_GEOMETRY.minHeight,
    })
  }
  const totalH =
    boxes.reduce((sum, box) => sum + box.height, 0) +
    MINDMAP_SUMMARY_CHILD_GAP_Y * (boxes.length - 1)
  let y = originY - totalH / 2
  children.forEach((child, index) => {
    const id = mindMapSummaryChildNodeId(summaryId, [...prefix, index])
    const width = boxes[index].width
    const height = boxes[index].height
    const x = outward === 1 ? originX : originX - width
    nodes.push(
      makeSummaryNode(id, child.text, x, y, style, {
        summaryId,
        summaryChildPath: [...prefix, index],
        mindMapSide: outward === 1 ? 'right' : 'left',
        mindMapDepth: prefix.length + 2,
      })
    )
    const nestedOriginX =
      outward === 1 ? x + width + MINDMAP_SUMMARY_CHILD_GAP_X : x - MINDMAP_SUMMARY_CHILD_GAP_X
    nodes.push(
      ...placeChildColumn(
        summaryId,
        child.children,
        nestedOriginX,
        y + height / 2,
        outward,
        style,
        widths,
        heights,
        [...prefix, index]
      )
    )
    y += height + MINDMAP_SUMMARY_CHILD_GAP_Y
  })
  return nodes
}

export function placeMindMapSummaryNodes(
  treeNodes: readonly DiagramNode[],
  connections: readonly Connection[],
  summaries: readonly MindMapSummarySpec[],
  data: DiagramData | null | undefined,
  widths: Record<string, number>,
  heights: Record<string, number>
): DiagramNode[] {
  const style = summaryStyle(data)
  const placed: DiagramNode[] = []
  const byPath = new Map<string, DiagramNode>()
  for (const node of treeNodes) {
    const path = mindMapLocationPathKey(node.id, connections)
    if (path) byPath.set(path, node)
  }

  for (const summary of summaries) {
    const boxes: SizedBox[] = []
    for (const path of summary.coveredPaths) {
      const node = byPath.get(path)
      if (!node) continue
      const box = nodeBox(node, widths, heights)
      if (box) boxes.push(box)
    }
    const union = unionBoxes(boxes)
    if (!union) continue

    const side = coveredSide(summary.coveredPaths)
    const outward: 1 | -1 = side === 'left' ? -1 : 1
    const rootId = mindMapSummaryRootNodeId(summary.id)
    const rootW = widths[rootId] ?? MIND_MAP_GEOMETRY.minWidth
    const rootH = heights[rootId] ?? MIND_MAP_GEOMETRY.minHeight
    const brace = mindMapSummaryBracePath(boxes, side, { kind: summary.kind ?? 'brace' })
    const tipX =
      brace?.tipX ??
      (side === 'right'
        ? union.x + union.width + MINDMAP_SUMMARY_BRACE_GAP
        : union.x - MINDMAP_SUMMARY_BRACE_GAP)
    const rootX =
      side === 'right'
        ? tipX + MINDMAP_SUMMARY_TIP_NODE_GAP
        : tipX - MINDMAP_SUMMARY_TIP_NODE_GAP - rootW
    const rootY = union.y + union.height / 2 - rootH / 2
    placed.push(
      makeSummaryNode(rootId, summary.text, rootX, rootY, style, {
        summaryId: summary.id,
        summaryChildPath: [],
        coveredPaths: summary.coveredPaths,
        mindMapSide: side,
        mindMapDepth: 1,
      })
    )
    const childOriginX =
      side === 'right'
        ? rootX + rootW + MINDMAP_SUMMARY_CHILD_GAP_X
        : rootX - MINDMAP_SUMMARY_CHILD_GAP_X
    placed.push(
      ...placeChildColumn(
        summary.id,
        summary.children,
        childOriginX,
        rootY + rootH / 2,
        outward,
        style,
        widths,
        heights,
        []
      )
    )
  }
  return placed
}

export function rematerializeMindMapSummaryNodes(
  data: DiagramData,
  widths: Record<string, number>,
  heights: Record<string, number>
): void {
  const summaries = readMindMapSummaries(data)
  const tree = filterTreeMindMapNodes(data.nodes)
  const placed = placeMindMapSummaryNodes(
    tree,
    data.connections ?? [],
    summaries,
    data,
    widths,
    heights
  )
  data.nodes = [...tree, ...placed]
}

export function mergeLaidOutTreeWithSummaries(
  laidOutTree: DiagramNode[],
  previousNodes: readonly DiagramNode[],
  connections: readonly Connection[],
  data: DiagramData | null | undefined,
  widths: Record<string, number>,
  heights: Record<string, number>
): DiagramNode[] {
  const summaries = readMindMapSummaries(data)
  if (summaries.length === 0 && !previousNodes.some((n) => isMindMapSummaryNode(n))) {
    return laidOutTree
  }
  const placed = placeMindMapSummaryNodes(
    laidOutTree,
    connections,
    summaries,
    data,
    widths,
    heights
  )
  return [...laidOutTree, ...placed]
}

export function coveredBoxesForSummary(
  treeNodes: readonly DiagramNode[],
  connections: readonly Connection[],
  summary: MindMapSummarySpec,
  widths: Record<string, number>,
  heights: Record<string, number>
): SizedBox[] {
  const boxes: SizedBox[] = []
  for (const path of summary.coveredPaths) {
    const node = treeNodes.find((item) => mindMapLocationPathKey(item.id, connections) === path)
    if (!node) continue
    const box = nodeBox(node, widths, heights)
    if (box) boxes.push(box)
  }
  return boxes
}

export type SummarySiblingBox = SizedBox & { path: string }

/** All same-parent siblings of a summary range, with laid-out boxes. */
export function siblingBoxesForSummary(
  treeNodes: readonly DiagramNode[],
  connections: readonly Connection[],
  summary: MindMapSummarySpec,
  widths: Record<string, number>,
  heights: Record<string, number>
): SummarySiblingBox[] {
  const paths = siblingPathsSharingParent(summary.coveredPaths, treeNodes, connections)
  const boxes: SummarySiblingBox[] = []
  for (const path of paths) {
    const node = treeNodes.find((item) => mindMapLocationPathKey(item.id, connections) === path)
    if (!node) continue
    const box = nodeBox(node, widths, heights)
    if (box) boxes.push({ path, ...box })
  }
  return boxes
}
