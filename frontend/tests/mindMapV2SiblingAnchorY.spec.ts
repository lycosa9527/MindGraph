import { describe, expect, it } from 'vitest'

import { DEFAULT_MINDMAP_BRANCH_GAP } from '@/composables/diagrams/layoutConfig'
import { recalculateMindMapV2ColumnPositions } from '@/stores/diagram/mindMapLayout'
import type { Connection, DiagramNode } from '@/types'
import { MINDMAP_NODE_UID_DATA_KEY } from '@/utils/mindMapNodeUid'
import {
  applyMindMapSideAnchorYPreserve,
  computeSymmetricRootStartYs,
} from '@/utils/mindMapSideStacking'

function node(
  id: string,
  y: number,
  opts?: { uid?: string; height?: number; width?: number; x?: number }
): DiagramNode {
  return {
    id,
    text: id,
    type: id === 'topic' ? 'topic' : 'branch',
    position: { x: opts?.x ?? 0, y },
    data: {
      ...(opts?.uid ? { [MINDMAP_NODE_UID_DATA_KEY]: opts.uid } : {}),
      estimatedHeight: opts?.height ?? 40,
      estimatedWidth: opts?.width ?? 80,
    },
  }
}

describe('v2 sibling Enter anchor Y stability', () => {
  const gap = DEFAULT_MINDMAP_BRANCH_GAP
  const topicCenterY = 0
  const h = 92
  const leaf = 40

  it('keeps the Enter anchor fixed after 2→3 left restack + preserve + recalc', () => {
    const beforeTops = computeSymmetricRootStartYs([h, h], topicCenterY, gap)
    const afterCentered = computeSymmetricRootStartYs([h, leaf, h], topicCenterY, gap)
    const anchorBeforeY = beforeTops[0]!

    // Leaf L1 roots (v2 new top-level sibling): pack origin is the root node Y.
    let nodes: DiagramNode[] = [
      node('topic', -20, { height: 40, width: 120, x: 400 }),
      node('branch-l-1-0', afterCentered[0]!, { uid: 'uid-a', height: h, x: 100 }),
      node('branch-l-1-1', afterCentered[1]!, { uid: 'uid-new', height: leaf, x: 100 }),
      node('branch-l-1-2', afterCentered[2]!, { uid: 'uid-b', height: h, x: 100 }),
      node('branch-r-1-0', beforeTops[0]!, { uid: 'uid-r0', height: h, x: 600 }),
      node('branch-r-1-1', beforeTops[1]!, { uid: 'uid-r1', height: h, x: 600 }),
    ]
    nodes = applyMindMapSideAnchorYPreserve(nodes, 'uid-a', anchorBeforeY)

    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-l-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-l-1-1' },
      { id: 'c2', source: 'topic', target: 'branch-l-1-2' },
      { id: 'c3', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c4', source: 'topic', target: 'branch-r-1-1' },
    ]

    const tallHeights: Record<string, number> = {
      topic: 40,
      'branch-l-1-0': h,
      'branch-l-1-1': leaf,
      'branch-l-1-2': h,
      'branch-r-1-0': h,
      'branch-r-1-1': h,
    }

    const { nodes: laidOut } = recalculateMindMapV2ColumnPositions(
      nodes,
      120,
      {},
      tallHeights,
      connections
    )

    const anchor = laidOut.find((n) => n.id === 'branch-l-1-0')
    const right0 = laidOut.find((n) => n.id === 'branch-r-1-0')
    expect(anchor?.position?.y).toBeCloseTo(anchorBeforeY, 5)
    expect(right0?.position?.y).toBeCloseTo(beforeTops[0]!, 5)
  })

  it('packs multi-root sides from the first child top when L1 has children', () => {
    // First L1 subtree starts at -100; L1 node itself is recentered lower.
    const nodes: DiagramNode[] = [
      node('topic', 0, { height: 40, width: 120, x: 400 }),
      node('branch-l-1-0', -74, { uid: 'uid-a', height: 40, x: 100 }),
      node('branch-l-2-1', -100, { uid: 'uid-a0', height: 40, x: 40 }),
      node('branch-l-2-2', -48, { uid: 'uid-a1', height: 40, x: 40 }),
      node('branch-l-1-3', 20, { uid: 'uid-b', height: 40, x: 100 }),
      node('branch-l-2-4', 20, { uid: 'uid-b0', height: 40, x: 40 }),
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-l-1-0' },
      { id: 'c1', source: 'branch-l-1-0', target: 'branch-l-2-1' },
      { id: 'c2', source: 'branch-l-1-0', target: 'branch-l-2-2' },
      { id: 'c3', source: 'topic', target: 'branch-l-1-3' },
      { id: 'c4', source: 'branch-l-1-3', target: 'branch-l-2-4' },
    ]
    const heights: Record<string, number> = {
      topic: 40,
      'branch-l-1-0': 40,
      'branch-l-2-1': 40,
      'branch-l-2-2': 40,
      'branch-l-1-3': 40,
      'branch-l-2-4': 40,
    }

    const { nodes: laidOut } = recalculateMindMapV2ColumnPositions(
      nodes,
      120,
      {},
      heights,
      connections
    )

    const firstChild = laidOut.find((n) => n.id === 'branch-l-2-1')
    expect(firstChild?.position?.y).toBeCloseTo(-100, 5)
  })
})
