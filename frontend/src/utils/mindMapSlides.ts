import type { Connection, DiagramNode } from '@/types'

import {
  buildMindMapOutlineTree,
  type MindMapOutlineNode,
} from '@/utils/mindMapOutlineTree'

export type MindMapSlideKind = 'overview' | 'branch'

export type MindMapSlideTraversalMode = 'firstLevel' | 'deep'

export interface MindMapSlide {
  id: string
  kind: MindMapSlideKind
  title: string
  focusNodeIds: string[]
  branchNodeId?: string
  /** Path from center topic to the current slide node (inclusive). */
  breadcrumb: string[]
}

function collectDeepTraversalNodes(root: MindMapOutlineNode): MindMapOutlineNode[] {
  const result: MindMapOutlineNode[] = []

  function walk(node: MindMapOutlineNode): void {
    for (const child of node.children) {
      result.push(child)
      walk(child)
    }
  }

  walk(root)
  return result
}

export function findMindMapBreadcrumb(
  root: MindMapOutlineNode,
  targetId: string
): string[] | null {
  if (root.id === targetId) return [root.text]
  for (const child of root.children) {
    const sub = findMindMapBreadcrumb(child, targetId)
    if (sub) return [root.text, ...sub]
  }
  return null
}

function slideForBranch(
  branch: MindMapOutlineNode,
  root: MindMapOutlineNode,
  getDescendantIds: (rootNodeId: string) => Set<string>
): MindMapSlide {
  return {
    id: branch.id,
    kind: 'branch',
    title: branch.text,
    branchNodeId: branch.id,
    breadcrumb: findMindMapBreadcrumb(root, branch.id) ?? [branch.text],
    focusNodeIds: [...getDescendantIds(branch.id)],
  }
}

export function buildMindMapSlides(
  nodes: DiagramNode[],
  connections: Connection[],
  getDescendantIds: (rootNodeId: string) => Set<string>,
  mode: MindMapSlideTraversalMode = 'firstLevel'
): MindMapSlide[] {
  if (!nodes.length) return []

  const outline = buildMindMapOutlineTree(nodes, connections)
  const root = outline[0]
  if (!root) return []

  const slides: MindMapSlide[] = [
    {
      id: 'overview',
      kind: 'overview',
      title: root.text,
      branchNodeId: root.id,
      breadcrumb: [root.text],
      focusNodeIds: nodes.map((n) => n.id),
    },
  ]

  const branchNodes =
    mode === 'deep' ? collectDeepTraversalNodes(root) : root.children

  for (const branch of branchNodes) {
    slides.push(slideForBranch(branch, root, getDescendantIds))
  }

  return slides
}
