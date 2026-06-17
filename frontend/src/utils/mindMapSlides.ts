import type { Connection, DiagramNode } from '@/types'

import { buildMindMapOutlineTree } from '@/utils/mindMapOutlineTree'

export type MindMapSlideKind = 'overview' | 'branch'

export interface MindMapSlide {
  id: string
  kind: MindMapSlideKind
  title: string
  focusNodeIds: string[]
  branchNodeId?: string
}

export function buildMindMapSlides(
  nodes: DiagramNode[],
  connections: Connection[],
  getDescendantIds: (rootNodeId: string) => Set<string>
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
      focusNodeIds: nodes.map((n) => n.id),
    },
  ]

  for (const branch of root.children) {
    slides.push({
      id: branch.id,
      kind: 'branch',
      title: branch.text,
      branchNodeId: branch.id,
      focusNodeIds: [...getDescendantIds(branch.id)],
    })
  }

  return slides
}
