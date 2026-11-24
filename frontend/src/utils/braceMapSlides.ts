/**
 * Node-carousel slides for brace maps.
 * - firstLevel: overview → each part (the part and everything under it)
 * - deep: overview → each part, then every descendant in tree order
 */
import type { Connection, DiagramNode } from '@/types'
import { BRACE_DIMENSION_LABEL_ID, findBraceMapWholeId } from '@/utils/braceMapIdentity'
import type { MindMapSlide, MindMapSlideTraversalMode } from '@/utils/mindMapSlides'

function nodeText(node: DiagramNode | undefined): string {
  if (!node) return ''
  return String(node.text ?? (node.data as { label?: string } | undefined)?.label ?? '').trim()
}

function childIds(
  parentId: string,
  connections: ReadonlyArray<Pick<Connection, 'source' | 'target'>>
): string[] {
  const ids: string[] = []
  for (const edge of connections) {
    if (edge.source === parentId && edge.target !== BRACE_DIMENSION_LABEL_ID) {
      ids.push(edge.target)
    }
  }
  return ids
}

function descendantsOf(
  rootId: string,
  connections: ReadonlyArray<Pick<Connection, 'source' | 'target'>>
): string[] {
  const ids: string[] = []
  function walk(id: string): void {
    for (const childId of childIds(id, connections)) {
      ids.push(childId)
      walk(childId)
    }
  }
  walk(rootId)
  return ids
}

function branchSlide(
  id: string,
  title: string,
  breadcrumb: string[],
  focusNodeIds: string[]
): MindMapSlide {
  return {
    id,
    kind: 'branch',
    title,
    branchNodeId: id,
    breadcrumb,
    focusNodeIds,
  }
}

export function buildBraceMapSlides(
  nodes: DiagramNode[],
  connections: ReadonlyArray<Connection>,
  mode: MindMapSlideTraversalMode = 'firstLevel'
): MindMapSlide[] {
  if (!nodes.length) return []
  const wholeId = findBraceMapWholeId(nodes, connections)
  if (!wholeId) return []

  const byId = new Map(nodes.map((node) => [node.id, node]))
  const whole = byId.get(wholeId)
  const rootTitle = nodeText(whole) || wholeId
  const contentIds = nodes
    .map((node) => node.id)
    .filter((id) => id && id !== BRACE_DIMENSION_LABEL_ID)
  const deep = mode === 'deep'

  const slides: MindMapSlide[] = [
    {
      id: 'overview',
      kind: 'overview',
      title: rootTitle,
      branchNodeId: wholeId,
      breadcrumb: [rootTitle],
      focusNodeIds: contentIds,
    },
  ]

  function pushNode(nodeId: string, ancestorIds: string[], ancestorTitles: string[]): void {
    const node = byId.get(nodeId)
    if (!node) return
    const title = nodeText(node) || nodeId
    const pathIds = [...ancestorIds, nodeId]
    const pathTitles = [...ancestorTitles, title]
    const under = descendantsOf(nodeId, connections)
    const focusPath = pathIds[0] === wholeId ? pathIds.slice(1) : pathIds
    slides.push(branchSlide(nodeId, title, pathTitles, [...focusPath, ...under]))
    if (!deep) return
    for (const childId of childIds(nodeId, connections)) {
      pushNode(childId, pathIds, pathTitles)
    }
  }

  for (const partId of childIds(wholeId, connections)) {
    pushNode(partId, [wholeId], [rootTitle])
  }

  return slides
}
