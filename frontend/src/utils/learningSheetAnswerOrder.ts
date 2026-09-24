/**
 * Reading order for 挖空支架图 reference answers.
 *
 * Mind maps use the same walk as branch numbering (`buildMindMapOutlineTree`):
 * each branch before the next, right column top→bottom, then the left column.
 * Numbering continues the left column clockwise (bottom→top). Otherwise the
 * left column is also top→bottom. Nodes the tree does not reach are appended
 * by canvas position. Other diagrams follow canvas position. Raw `nodes[]`
 * order is insertion order and drifts after layout and edits.
 */
import type { Connection, DiagramNode, DiagramType } from '@/types'
import { buildMindMapOutlineTree, flattenMindMapOutline } from '@/utils/mindMapOutlineTree'

function isMindMapType(diagramType: string | null | undefined): boolean {
  return diagramType === 'mindmap' || diagramType === 'mind_map'
}

function visualCompare(a: DiagramNode, b: DiagramNode, indexById: Map<string, number>): number {
  const ay = a.position?.y ?? 0
  const by = b.position?.y ?? 0
  if (ay !== by) return ay - by
  const ax = a.position?.x ?? 0
  const bx = b.position?.x ?? 0
  if (ax !== bx) return ax - bx
  return (indexById.get(a.id) ?? 0) - (indexById.get(b.id) ?? 0)
}

function sortByCanvasPosition(nodes: readonly DiagramNode[]): DiagramNode[] {
  const indexById = new Map(nodes.map((node, index) => [node.id, index]))
  return nodes.slice().sort((a, b) => visualCompare(a, b, indexById))
}

/** Nodes in the order a reader meets them on the canvas. */
export function nodesInLearningSheetReadingOrder(
  nodes: readonly DiagramNode[],
  connections: readonly Connection[],
  diagramType: DiagramType | string | null | undefined,
  branchNumbering = false
): DiagramNode[] {
  if (!isMindMapType(diagramType) || nodes.length === 0) {
    return sortByCanvasPosition(nodes)
  }
  const tree = buildMindMapOutlineTree(nodes.slice(), connections.slice(), {
    clockwiseLeft: branchNumbering,
  })
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const ordered: DiagramNode[] = []
  const seen = new Set<string>()
  for (const row of flattenMindMapOutline(tree)) {
    const node = byId.get(row.id)
    if (!node || seen.has(node.id)) continue
    seen.add(node.id)
    ordered.push(node)
  }
  ordered.push(...sortByCanvasPosition(nodes.filter((node) => !seen.has(node.id))))
  return ordered
}
