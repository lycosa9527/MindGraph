import { describe, expect, it } from 'vitest'

import {
  DEFAULT_MINDMAP_BRANCH_GAP,
  DEFAULT_MINDMAP_RANK_SEPARATION,
} from '@/composables/diagrams/layoutConfig'
import { MINDMAP_UNDERLINE_STROKE_WIDTH, mindMapConnectionAnchorY } from '@/config/mindMapGeometry'
import { mergeMindMapLayoutPositions } from '@/stores/diagram/mindMapDisplayLayout'
import { recalculateMindMapV2ColumnPositions } from '@/stores/diagram/mindMapLayout'
import type { Connection, DiagramNode } from '@/types'
import { MINDMAP_NODE_UID_DATA_KEY } from '@/utils/mindMapNodeUid'
import {
  applyMindMapIncrementalTopLevelSiblingLayout,
  applyMindMapL1HeightDeltaShift,
  centerMindMapChildrenGroupsOnParents,
  centerMindMapSidePacksOnTopic,
  computeSymmetricRootStartYs,
  resolveMindMapSiblingSubtreeOverlaps,
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

function requireAt<T>(arr: readonly T[], index: number, label = 'array'): T {
  const value = arr[index]
  if (value === undefined) throw new Error(`expected ${label}[${index}]`)
  return value
}

function requireDefined<T>(value: T | null | undefined, label: string): T {
  if (value == null) throw new Error(`expected ${label}`)
  return value
}

function requireNode(nodes: DiagramNode[], id: string): DiagramNode {
  const found = nodes.find((n) => n.id === id)
  if (!found) throw new Error(`expected node ${id}`)
  return found
}

function requirePosition(nodeEntry: DiagramNode, id: string): { x: number; y: number } {
  const pos = nodeEntry.position
  if (!pos) throw new Error(`expected position for ${id}`)
  return pos
}

describe('v2 sibling Enter anchor Y stability', () => {
  const gap = DEFAULT_MINDMAP_BRANCH_GAP
  const topicCenterY = 0
  const h = 92
  const leaf = 40

  it('keeps Enter L1 gaps and centers each side pack on the topic', () => {
    const beforeTops = computeSymmetricRootStartYs([h, h], topicCenterY, gap)
    const anchorBeforeY = requireAt(beforeTops, 0, 'beforeTops')
    const lowerBeforeY = requireAt(beforeTops, 1, 'beforeTops')
    const topicBeforeY = -20

    // Before: 分支4 (with kids) + 分支3. After reload: symmetric 3-root restack.
    const beforeNodes: DiagramNode[] = [
      node('topic', topicBeforeY, { height: 40, width: 120, x: 400 }),
      node('branch-l-1-0', anchorBeforeY, { uid: 'uid-a', height: 40, x: 100 }),
      node('branch-l-2-1', anchorBeforeY - 26, { uid: 'uid-a0', height: 40, x: 40 }),
      node('branch-l-2-2', anchorBeforeY + 26, { uid: 'uid-a1', height: 40, x: 40 }),
      node('branch-l-1-3', lowerBeforeY, { uid: 'uid-b', height: h, x: 100 }),
      node('branch-r-1-0', requireAt(beforeTops, 0, 'beforeTops'), {
        uid: 'uid-r0',
        height: h,
        x: 600,
      }),
      node('branch-r-1-1', requireAt(beforeTops, 1, 'beforeTops'), {
        uid: 'uid-r1',
        height: h,
        x: 600,
      }),
    ]

    const afterCentered = computeSymmetricRootStartYs([h, leaf, h], topicCenterY, gap)
    const afterCentered0 = requireAt(afterCentered, 0, 'afterCentered')
    const afterCentered1 = requireAt(afterCentered, 1, 'afterCentered')
    const afterCentered2 = requireAt(afterCentered, 2, 'afterCentered')
    const afterNodes: DiagramNode[] = [
      node('topic', topicBeforeY + 34, { height: 40, width: 120, x: 400 }),
      node('branch-l-1-0', afterCentered0, { uid: 'uid-a', height: 40, x: 100 }),
      node('branch-l-2-1', afterCentered0 - 26, { uid: 'uid-a0', height: 40, x: 40 }),
      node('branch-l-2-2', afterCentered0 + 26, { uid: 'uid-a1', height: 40, x: 40 }),
      node('branch-l-1-1', afterCentered1, { uid: 'uid-new', height: leaf, x: 100 }),
      node('branch-l-1-2', afterCentered2, { uid: 'uid-b', height: h, x: 100 }),
      node('branch-r-1-0', requireAt(beforeTops, 0, 'beforeTops'), {
        uid: 'uid-r0',
        height: h,
        x: 600,
      }),
      node('branch-r-1-1', requireAt(beforeTops, 1, 'beforeTops'), {
        uid: 'uid-r1',
        height: h,
        x: 600,
      }),
    ]

    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-l-1-0' },
      { id: 'c1', source: 'branch-l-1-0', target: 'branch-l-2-1' },
      { id: 'c2', source: 'branch-l-1-0', target: 'branch-l-2-2' },
      { id: 'c3', source: 'topic', target: 'branch-l-1-1' },
      { id: 'c4', source: 'topic', target: 'branch-l-1-2' },
      { id: 'c5', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c6', source: 'topic', target: 'branch-r-1-1' },
    ]

    const nodes = applyMindMapIncrementalTopLevelSiblingLayout(
      beforeNodes,
      afterNodes,
      connections,
      {
        anchorUid: 'uid-a',
        newSiblingUid: 'uid-new',
        insert: 'below',
        topicY: topicBeforeY,
      }
    )

    const heights: Record<string, number> = {
      topic: 40,
      'branch-l-1-0': 40,
      'branch-l-2-1': 40,
      'branch-l-2-2': 40,
      'branch-l-1-1': leaf,
      'branch-l-1-2': h,
      'branch-r-1-0': h,
      'branch-r-1-1': h,
    }

    // First paint path: preserveIncomingY keeps L1 Enter gaps (no full restack).
    // Formal = center anchors on all depths so this case isolates L1 gap preserve.
    const { nodes: firstPaint } = recalculateMindMapV2ColumnPositions(
      nodes,
      120,
      {},
      heights,
      connections,
      new Set(),
      'formal',
      { preserveIncomingY: true }
    )

    const anchor = firstPaint.find((n) => n.id === 'branch-l-1-0')
    const created = firstPaint.find((n) => n.id === 'branch-l-1-1')
    const lower = firstPaint.find((n) => n.id === 'branch-l-1-2')
    const topic = firstPaint.find((n) => n.id === 'topic')
    const child = firstPaint.find((n) => n.id === 'branch-l-2-1')

    const topicNode = requireNode(nodes, 'topic')
    const anchorNode = requireNode(nodes, 'branch-l-1-0')
    const childNode = requireNode(nodes, 'branch-l-2-1')
    const anchorResolved = requireDefined(anchor, 'anchor')
    const createdResolved = requireDefined(created, 'created')
    const lowerResolved = requireDefined(lower, 'lower')
    const topicResolved = requireDefined(topic, 'topic')

    // Topic stays; side packs from incremental layout are already topic-centered.
    expect(topic?.position?.y).toBeCloseTo(requirePosition(topicNode, 'topic').y, 5)
    expect(anchor?.position?.y).toBeCloseTo(requirePosition(anchorNode, 'branch-l-1-0').y, 5)
    expect(child?.position?.y).toBeCloseTo(requirePosition(childNode, 'branch-l-2-1').y, 5)
    // Enter gap preserved: new sibling still below the anchor.
    expect(created?.position?.y).toBeGreaterThan(requirePosition(anchorResolved, 'branch-l-1-0').y)
    expect(requirePosition(lowerResolved, 'branch-l-1-2').y).toBeGreaterThan(
      requirePosition(createdResolved, 'branch-l-1-1').y
    )
    // Left L1 midpoint ≈ topic center.
    const leftAnchors = [anchorResolved, createdResolved, lowerResolved].map(
      (n) => requirePosition(n, n.id).y + (heights[n.id] ?? 40) / 2
    )
    const leftMid = (Math.min(...leftAnchors) + Math.max(...leftAnchors)) / 2
    const topicCenter = requirePosition(topicResolved, 'topic').y + heights.topic / 2
    expect(leftMid).toBeCloseTo(topicCenter, 5)
  })

  it('under preserve, rigid-centers children groups and separates overlapping L1 fans', () => {
    // Parent sits at the top of a 4-child stack (Enter-below bias) — not centered.
    const nodes: DiagramNode[] = [
      node('topic', 0, { height: 40, width: 120, x: 400 }),
      node('branch-l-1-0', -80, { uid: 'uid-a', height: 40, x: 100 }),
      node('branch-l-2-1', -80, { uid: 'uid-a0', height: 40, x: 40 }),
      node('branch-l-2-2', -28, { uid: 'uid-a1', height: 40, x: 40 }),
      node('branch-l-2-3', 24, { uid: 'uid-a2', height: 40, x: 40 }),
      node('branch-l-2-4', 76, { uid: 'uid-a3', height: 40, x: 40 }),
      node('branch-l-1-5', 120, { uid: 'uid-b', height: 40, x: 100 }),
      node('branch-r-1-0', 0, { uid: 'uid-r', height: 40, x: 600 }),
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-l-1-0' },
      { id: 'c1', source: 'branch-l-1-0', target: 'branch-l-2-1' },
      { id: 'c2', source: 'branch-l-1-0', target: 'branch-l-2-2' },
      { id: 'c3', source: 'branch-l-1-0', target: 'branch-l-2-3' },
      { id: 'c4', source: 'branch-l-1-0', target: 'branch-l-2-4' },
      { id: 'c5', source: 'topic', target: 'branch-l-1-5' },
      { id: 'c6', source: 'topic', target: 'branch-r-1-0' },
    ]
    const heights: Record<string, number> = {
      topic: 40,
      'branch-l-1-0': 40,
      'branch-l-2-1': 40,
      'branch-l-2-2': 40,
      'branch-l-2-3': 40,
      'branch-l-2-4': 40,
      'branch-l-1-5': 40,
      'branch-r-1-0': 40,
    }

    const childGapBefore =
      requirePosition(requireNode(nodes, 'branch-l-2-2'), 'branch-l-2-2').y -
      requirePosition(requireNode(nodes, 'branch-l-2-1'), 'branch-l-2-1').y

    const { nodes: laidOut } = recalculateMindMapV2ColumnPositions(
      nodes,
      120,
      {},
      heights,
      connections,
      new Set(),
      'classic',
      { preserveIncomingY: true }
    )

    const parent = requireNode(laidOut, 'branch-l-1-0')
    const kids = ['branch-l-2-1', 'branch-l-2-2', 'branch-l-2-3', 'branch-l-2-4'].map((id) =>
      requireNode(laidOut, id)
    )
    // Classic: L1 rounded (center), L2 underline (bottom) — match edge routing.
    const parentPos = requirePosition(parent, 'branch-l-1-0')
    const parentAnchor = mindMapConnectionAnchorY(parentPos.y, heights['branch-l-1-0'], 'rounded')
    const kidAnchors = kids.map((n) =>
      mindMapConnectionAnchorY(requirePosition(n, n.id).y, 40, 'underline')
    )
    const kidMid = (Math.min(...kidAnchors) + Math.max(...kidAnchors)) / 2
    expect(kidMid).toBeCloseTo(parentAnchor, 5)

    // Sibling gaps among children preserved (rigid slide).
    const kid0Pos = requirePosition(kids[0], kids[0].id)
    const kid1Pos = requirePosition(requireDefined(kids[1], 'kids[1]'), 'branch-l-2-2')
    expect(kid1Pos.y - kid0Pos.y).toBeCloseTo(childGapBefore, 5)
    // Neighboring L1 fan cleared by at least the cross-branch gap.
    const lower = requireNode(laidOut, 'branch-l-1-5')
    const upperFanBottom = Math.max(...kids.map((n) => requirePosition(n, n.id).y + 40))
    const lowerPos = requirePosition(lower, 'branch-l-1-5')
    expect(lowerPos.y).toBeGreaterThanOrEqual(upperFanBottom + DEFAULT_MINDMAP_BRANCH_GAP - 0.5)
    expect(lowerPos.y).toBeGreaterThan(parentPos.y)
  })

  it('resolveMindMapSiblingSubtreeOverlaps pushes lower L1 fan below upper fan', () => {
    // Mimic screenshot: 分支1 kids overlap 分支2 kids when L1 tops stay pinned.
    const nodes: DiagramNode[] = [
      node('topic', 0, { height: 40, width: 120, x: 400 }),
      node('branch-r-1-0', -20, { height: 40, x: 600 }),
      node('branch-r-2-1', -40, { height: 34, x: 700 }),
      node('branch-r-2-2', 10, { height: 34, x: 700 }),
      node('branch-r-1-1', 40, { height: 40, x: 600 }),
      node('branch-r-2-3', 20, { height: 34, x: 700 }),
      node('branch-r-2-4', 60, { height: 34, x: 700 }),
      node('branch-r-2-5', 100, { height: 34, x: 700 }),
      node('branch-r-2-6', 140, { height: 34, x: 700 }),
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'branch-r-1-0', target: 'branch-r-2-1' },
      { id: 'c2', source: 'branch-r-1-0', target: 'branch-r-2-2' },
      { id: 'c3', source: 'topic', target: 'branch-r-1-1' },
      { id: 'c4', source: 'branch-r-1-1', target: 'branch-r-2-3' },
      { id: 'c5', source: 'branch-r-1-1', target: 'branch-r-2-4' },
      { id: 'c6', source: 'branch-r-1-1', target: 'branch-r-2-5' },
      { id: 'c7', source: 'branch-r-1-1', target: 'branch-r-2-6' },
    ]
    const heights: Record<string, number> = Object.fromEntries(
      nodes.map((n) => [n.id, (n.data?.estimatedHeight as number) ?? 40])
    )

    // Precondition: fans overlap vertically.
    expect(10 + 34).toBeGreaterThan(20)

    const separated = resolveMindMapSiblingSubtreeOverlaps(nodes, connections, heights)
    const upperBottom =
      requirePosition(requireNode(separated, 'branch-r-2-2'), 'branch-r-2-2').y + 34
    const lowerTop = requirePosition(requireNode(separated, 'branch-r-2-3'), 'branch-r-2-3').y
    expect(lowerTop).toBeGreaterThanOrEqual(upperBottom + DEFAULT_MINDMAP_BRANCH_GAP - 0.5)
    // Lower L1 stays below upper L1; order preserved.
    expect(
      requirePosition(requireNode(separated, 'branch-r-1-1'), 'branch-r-1-1').y
    ).toBeGreaterThan(requirePosition(requireNode(separated, 'branch-r-1-0'), 'branch-r-1-0').y)
  })

  it('centerMindMapChildrenGroupsOnParents aligns connection anchors (classic underline L2)', () => {
    const nodes: DiagramNode[] = [
      node('topic', 0, { height: 40 }),
      node('branch-r-1-0', 0, { height: 40 }),
      node('branch-r-2-1', 0, { height: 40 }),
      node('branch-r-2-2', 60, { height: 40 }),
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'branch-r-1-0', target: 'branch-r-2-1' },
      { id: 'c2', source: 'branch-r-1-0', target: 'branch-r-2-2' },
    ]
    const centered = centerMindMapChildrenGroupsOnParents(
      nodes,
      connections,
      undefined,
      undefined,
      'classic'
    )
    expect(centered.find((n) => n.id === 'branch-r-1-0')?.position?.y).toBeCloseTo(0, 5)
    // Parent rounded anchor 20; child underline anchors were 39 and 99 → mid 69 → delta -49.
    const underlineHalf = MINDMAP_UNDERLINE_STROKE_WIDTH / 2
    const expectedDelta = 20 - (0 + 40 - underlineHalf + 60 + 40 - underlineHalf) / 2
    expect(centered.find((n) => n.id === 'branch-r-2-1')?.position?.y).toBeCloseTo(
      0 + expectedDelta,
      5
    )
    expect(centered.find((n) => n.id === 'branch-r-2-2')?.position?.y).toBeCloseTo(
      60 + expectedDelta,
      5
    )
  })

  it('pins L1 relative gaps and centers the side pack on the topic', () => {
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

    // Topic stays; pack slides so L1 mid (-54…40 → -7) aligns with topic center 20.
    expect(laidOut.find((n) => n.id === 'topic')?.position?.y).toBeCloseTo(0, 5)
    expect(laidOut.find((n) => n.id === 'branch-l-1-0')?.position?.y).toBeCloseTo(-47, 5)
    expect(laidOut.find((n) => n.id === 'branch-l-1-3')?.position?.y).toBeCloseTo(47, 5)
    // Relative gap between the two L1 roots preserved (was 94).
    expect(
      (laidOut.find((n) => n.id === 'branch-l-1-3')?.position?.y ?? 0) -
        (laidOut.find((n) => n.id === 'branch-l-1-0')?.position?.y ?? 0)
    ).toBeCloseTo(94, 5)
  })

  it('keeps left L1 on one outer column when measured widths differ (edit-end / canvas click)', () => {
    const topicW = 120
    const topicX = 400
    const nodes: DiagramNode[] = [
      node('topic', 0, { height: 40, width: topicW, x: topicX }),
      node('branch-l-1-0', -80, { uid: 'uid-wide', height: 40, width: 140, x: 200 }),
      node('branch-l-1-1', 0, { uid: 'uid-new', height: 40, width: 70, x: 250 }),
      node('branch-l-1-2', 80, { uid: 'uid-mid', height: 40, width: 100, x: 220 }),
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-l-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-l-1-1' },
      { id: 'c2', source: 'topic', target: 'branch-l-1-2' },
    ]
    const widths: Record<string, number> = {
      'branch-l-1-0': 140,
      'branch-l-1-1': 70,
      'branch-l-1-2': 100,
    }

    const { nodes: laidOut } = recalculateMindMapV2ColumnPositions(
      nodes,
      topicW,
      widths,
      { topic: 40, 'branch-l-1-0': 40, 'branch-l-1-1': 40, 'branch-l-1-2': 40 },
      connections,
      new Set(),
      undefined,
      { preserveIncomingY: true }
    )

    const wide = laidOut.find((n) => n.id === 'branch-l-1-0')
    const fresh = laidOut.find((n) => n.id === 'branch-l-1-1')
    const mid = laidOut.find((n) => n.id === 'branch-l-1-2')
    expect(wide?.position?.x).toBeDefined()
    const wideResolved = requireDefined(wide, 'wide')
    const widePos = requirePosition(wideResolved, 'branch-l-1-0')
    expect(fresh?.position?.x).toBeCloseTo(widePos.x, 5)
    expect(mid?.position?.x).toBeCloseTo(widePos.x, 5)

    // Column is max L1 width from the topic's left edge.
    const expectedX = topicX - DEFAULT_MINDMAP_RANK_SEPARATION - 140
    expect(wide?.position?.x).toBeCloseTo(expectedX, 5)
  })

  it('pushes same-side L1 roots below when an L1 height grows under preserve', () => {
    const nodes: DiagramNode[] = [
      node('topic', 0, { height: 40, width: 120, x: 400 }),
      node('branch-l-1-0', -40, { uid: 'uid-a', height: 40, x: 100 }),
      node('branch-l-2-1', -50, { uid: 'uid-a0', height: 30, x: 40 }),
      node('branch-l-1-1', 40, { uid: 'uid-b', height: 40, x: 100 }),
      node('branch-l-2-2', 50, { uid: 'uid-b0', height: 30, x: 40 }),
      node('branch-r-1-0', 0, { uid: 'uid-r', height: 40, x: 600 }),
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-l-1-0' },
      { id: 'c1', source: 'branch-l-1-0', target: 'branch-l-2-1' },
      { id: 'c2', source: 'topic', target: 'branch-l-1-1' },
      { id: 'c3', source: 'branch-l-1-1', target: 'branch-l-2-2' },
      { id: 'c4', source: 'topic', target: 'branch-r-1-0' },
    ]

    const shifted = applyMindMapL1HeightDeltaShift(nodes, connections, 'branch-l-1-0', 20)

    // After push-below + per-side center: topic fixed, left pack recentered.
    expect(shifted.find((n) => n.id === 'topic')?.position?.y).toBeCloseTo(0, 5)
    expect(shifted.find((n) => n.id === 'branch-r-1-0')?.position?.y).toBeCloseTo(0, 5)
    // Pre-center left was -40/-50/60/70; mid of L1 anchors (-20,80)=30 → delta -10.
    expect(shifted.find((n) => n.id === 'branch-l-1-0')?.position?.y).toBeCloseTo(-50, 5)
    expect(shifted.find((n) => n.id === 'branch-l-2-1')?.position?.y).toBeCloseTo(-60, 5)
    expect(shifted.find((n) => n.id === 'branch-l-1-1')?.position?.y).toBeCloseTo(50, 5)
    expect(shifted.find((n) => n.id === 'branch-l-2-2')?.position?.y).toBeCloseTo(60, 5)
    const centered = centerMindMapSidePacksOnTopic(
      [
        node('topic', 0, { height: 40 }),
        node('branch-l-1-0', -40, { height: 40 }),
        node('branch-l-1-1', 60, { height: 40 }),
        node('branch-r-1-0', 0, { height: 40 }),
      ],
      [
        { id: 'c0', source: 'topic', target: 'branch-l-1-0' },
        { id: 'c1', source: 'topic', target: 'branch-l-1-1' },
        { id: 'c2', source: 'topic', target: 'branch-r-1-0' },
      ]
    )
    expect(centered.find((n) => n.id === 'branch-l-1-0')?.position?.y).toBeCloseTo(-50, 5)
  })

  it('centers short multi-child underline fan on parent connection anchor', () => {
    // Taller L1 (80) with two short underline kids (28): box-span mid left
    // underlines below the stem; anchors must match parent mid.
    const nodes: DiagramNode[] = [
      node('topic', 0, { height: 40, width: 120, x: 400 }),
      node('branch-r-1-0', 100, { height: 80, width: 100, x: 560 }),
      node('branch-r-2-1', 100, { height: 28, width: 80, x: 700 }),
      node('branch-r-2-2', 140, { height: 28, width: 80, x: 700 }),
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'branch-r-1-0', target: 'branch-r-2-1' },
      { id: 'c2', source: 'branch-r-1-0', target: 'branch-r-2-2' },
    ]
    const heights: Record<string, number> = {
      topic: 40,
      'branch-r-1-0': 80,
      'branch-r-2-1': 28,
      'branch-r-2-2': 28,
    }

    const { nodes: laidOut } = recalculateMindMapV2ColumnPositions(
      nodes,
      120,
      {},
      heights,
      connections,
      new Set(),
      'classic'
    )

    const parent = requireNode(laidOut, 'branch-r-1-0')
    const kid1 = requireNode(laidOut, 'branch-r-2-1')
    const kid2 = requireNode(laidOut, 'branch-r-2-2')
    const parentPos = requirePosition(parent, 'branch-r-1-0')
    const parentAnchor = mindMapConnectionAnchorY(parentPos.y, heights['branch-r-1-0'], 'rounded')
    const kidMid =
      (mindMapConnectionAnchorY(requirePosition(kid1, 'branch-r-2-1').y, 28, 'underline') +
        mindMapConnectionAnchorY(requirePosition(kid2, 'branch-r-2-2').y, 28, 'underline')) /
      2
    expect(kidMid).toBeCloseTo(parentAnchor, 5)
  })

  it('aligns sole underline child (and chain) to parent mid so the stem stays flat', () => {
    // Right-side regression: L1→L2→L3 used box-mid centering, so the L2 underline
    // sat below the L1 mid and the connector sloped. Left sole leaves already worked.
    const nodes: DiagramNode[] = [
      node('topic', 0, { height: 40, width: 120, x: 400 }),
      node('branch-r-1-0', 0, { height: 40, width: 100, x: 560 }),
      node('branch-r-2-1', 40, { height: 28, width: 80, x: 700 }),
      node('branch-r-3-1', 80, { height: 28, width: 80, x: 820 }),
      node('branch-l-1-0', 0, { height: 40, width: 100, x: 200 }),
      node('branch-l-2-1', 40, { height: 28, width: 80, x: 40 }),
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'branch-r-1-0', target: 'branch-r-2-1' },
      { id: 'c2', source: 'branch-r-2-1', target: 'branch-r-3-1' },
      { id: 'c3', source: 'topic', target: 'branch-l-1-0' },
      { id: 'c4', source: 'branch-l-1-0', target: 'branch-l-2-1' },
    ]
    const heights: Record<string, number> = {
      topic: 40,
      'branch-r-1-0': 40,
      'branch-r-2-1': 28,
      'branch-r-3-1': 28,
      'branch-l-1-0': 40,
      'branch-l-2-1': 28,
    }

    const { nodes: laidOut } = recalculateMindMapV2ColumnPositions(
      nodes,
      120,
      {},
      heights,
      connections,
      new Set(),
      'classic'
    )

    const rightL1 = requireNode(laidOut, 'branch-r-1-0')
    const rightL2 = requireNode(laidOut, 'branch-r-2-1')
    const rightL3 = requireNode(laidOut, 'branch-r-3-1')
    const leftL1 = requireNode(laidOut, 'branch-l-1-0')
    const leftL2 = requireNode(laidOut, 'branch-l-2-1')

    const rightParentAnchor = mindMapConnectionAnchorY(
      requirePosition(rightL1, 'branch-r-1-0').y,
      heights['branch-r-1-0'],
      'rounded'
    )
    const rightL2Anchor = mindMapConnectionAnchorY(
      requirePosition(rightL2, 'branch-r-2-1').y,
      heights['branch-r-2-1'],
      'underline'
    )
    const rightL3Anchor = mindMapConnectionAnchorY(
      requirePosition(rightL3, 'branch-r-3-1').y,
      heights['branch-r-3-1'],
      'underline'
    )
    expect(rightL2Anchor).toBeCloseTo(rightParentAnchor, 5)
    expect(rightL3Anchor).toBeCloseTo(rightParentAnchor, 5)

    const leftParentAnchor = mindMapConnectionAnchorY(
      requirePosition(leftL1, 'branch-l-1-0').y,
      heights['branch-l-1-0'],
      'rounded'
    )
    const leftL2Anchor = mindMapConnectionAnchorY(
      requirePosition(leftL2, 'branch-l-2-1').y,
      heights['branch-l-2-1'],
      'underline'
    )
    expect(leftL2Anchor).toBeCloseTo(leftParentAnchor, 5)
  })

  it('sole underline L1 aligns to topic without skewing its children', () => {
    const heights = {
      topic: 48,
      'branch-l-1-0': 36,
      'branch-l-2-0': 36,
      'branch-l-2-1': 36,
      'branch-r-1-0': 36,
      'branch-r-1-1': 36,
    }
    const nodes: DiagramNode[] = [
      node('topic', 200, { height: 48, width: 120, x: 400 }),
      // Intentionally high — sole left must snap to topic and keep the fan.
      node('branch-l-1-0', 100, { height: 36, width: 80, x: 100 }),
      node('branch-l-2-0', 80, { height: 36, width: 70, x: 20 }),
      node('branch-l-2-1', 130, { height: 36, width: 70, x: 20 }),
      node('branch-r-1-0', 150, { height: 36, width: 80, x: 600 }),
      node('branch-r-1-1', 250, { height: 36, width: 80, x: 600 }),
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-l-1-0' },
      { id: 'c1', source: 'branch-l-1-0', target: 'branch-l-2-0' },
      { id: 'c2', source: 'branch-l-1-0', target: 'branch-l-2-1' },
      { id: 'c3', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c4', source: 'topic', target: 'branch-r-1-1' },
    ]
    const { nodes: next } = recalculateMindMapV2ColumnPositions(
      nodes,
      120,
      {},
      heights,
      connections,
      new Set(),
      'underline'
    )
    const topicY = requirePosition(requireNode(next, 'topic'), 'topic').y
    const leftY = requirePosition(requireNode(next, 'branch-l-1-0'), 'branch-l-1-0').y
    const k0Y = requirePosition(requireNode(next, 'branch-l-2-0'), 'branch-l-2-0').y
    const k1Y = requirePosition(requireNode(next, 'branch-l-2-1'), 'branch-l-2-1').y
    const topicAnchor = mindMapConnectionAnchorY(topicY, heights.topic, 'rectangle')
    const leftAnchor = mindMapConnectionAnchorY(leftY, heights['branch-l-1-0'], 'underline')
    const kidMid =
      (mindMapConnectionAnchorY(k0Y, heights['branch-l-2-0'], 'underline') +
        mindMapConnectionAnchorY(k1Y, heights['branch-l-2-1'], 'underline')) /
      2
    expect(leftAnchor).toBeCloseTo(topicAnchor, 5)
    expect(kidMid).toBeCloseTo(leftAnchor, 5)
  })

  it('mergeMindMapLayoutPositions writes X back and skips no-op', () => {
    const store: DiagramNode[] = [
      node('topic', 0, { x: 400, width: 120 }),
      node('branch-l-1-0', 10, { x: 200, width: 80 }),
    ]
    const laidOut: DiagramNode[] = [
      node('topic', 0, { x: 400, width: 120 }),
      node('branch-l-1-0', 10, { x: 180, width: 80 }),
    ]
    const merged = mergeMindMapLayoutPositions(store, laidOut)
    expect(merged).not.toBe(store)
    expect(merged.find((n) => n.id === 'branch-l-1-0')?.position?.x).toBeCloseTo(180, 5)

    const again = mergeMindMapLayoutPositions(merged, laidOut)
    expect(again).toBe(merged)
  })
})
