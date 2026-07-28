import { describe, expect, it } from 'vitest'

import { DEFAULT_MINDMAP_BRANCH_GAP } from '@/composables/diagrams/layoutConfig'
import type { DiagramNode } from '@/types'
import type { Connection } from '@/types'
import { MINDMAP_NODE_UID_DATA_KEY } from '@/utils/mindMapNodeUid'
import {
  applyMindMapIncrementalSiblingYPreserve,
  applyMindMapIncrementalTopLevelSiblingLayout,
  applyMindMapSideAnchorYPreserve,
  applyMindMapTopicYPreserve,
  computeSequentialRootStartYsFrom,
  computeSymmetricRootStartYs,
} from '@/utils/mindMapSideStacking'

describe('computeSymmetricRootStartYs', () => {
  const gap = DEFAULT_MINDMAP_BRANCH_GAP
  const topic = 0

  it('centers a single root on the topic', () => {
    expect(computeSymmetricRootStartYs([92], topic, gap)).toEqual([-46])
  })

  it('packs two equal roots the same as sequential (no Math.max special case)', () => {
    const spans = [92, 92]
    const centered = computeSymmetricRootStartYs(spans, topic, gap)
    const fromTop = computeSequentialRootStartYsFrom(centered[0], spans, gap)
    expect(centered).toEqual(fromTop)
    const c0 = centered[0]
    const c1 = centered[1]
    const s0 = spans[0]
    expect(c0).toBeDefined()
    expect(c1).toBeDefined()
    expect(s0).toBeDefined()
    if (c0 === undefined || c1 === undefined || s0 === undefined) {
      throw new Error('expected centered root start Y values')
    }
    expect(c1 - (c0 + s0)).toBe(gap)
  })

  it('keeps the cross-branch gap when two roots have unequal spans', () => {
    const spans = [144, 92]
    const tops = computeSymmetricRootStartYs(spans, topic, gap)
    const t0 = tops[0]
    const t1 = tops[1]
    const s0 = spans[0]
    expect(t0).toBeDefined()
    expect(t1).toBeDefined()
    expect(s0).toBeDefined()
    if (t0 === undefined || t1 === undefined || s0 === undefined) {
      throw new Error('expected root start Y values')
    }
    expect(t1 - (t0 + s0)).toBe(gap)
  })

  it('packs three roots sequentially around the topic', () => {
    const spans = [92, 40, 92]
    const tops = computeSymmetricRootStartYs(spans, topic, gap)
    expect(tops).toHaveLength(3)
    const t0 = tops[0]
    const t1 = tops[1]
    const t2 = tops[2]
    const s0 = spans[0]
    const s1 = spans[1]
    expect(t0).toBeDefined()
    expect(t1).toBeDefined()
    expect(t2).toBeDefined()
    expect(s0).toBeDefined()
    expect(s1).toBeDefined()
    if (
      t0 === undefined ||
      t1 === undefined ||
      t2 === undefined ||
      s0 === undefined ||
      s1 === undefined
    ) {
      throw new Error('expected root start Y values')
    }
    expect(t1 - (t0 + s0)).toBe(gap)
    expect(t2 - (t1 + s1)).toBe(gap)
    const total = spans.reduce((a, b) => a + b, 0) + 2 * gap
    expect(tops[0]).toBeCloseTo(topic - total / 2, 5)
  })
})

describe('applyMindMapSideAnchorYPreserve', () => {
  function branch(id: string, uid: string, y: number): DiagramNode {
    return {
      id,
      text: id,
      type: 'branch',
      position: { x: 0, y },
      data: { [MINDMAP_NODE_UID_DATA_KEY]: uid },
    }
  }

  it('translates only the anchor side so the uid keeps its prior Y', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic', position: { x: 0, y: 100 } },
      branch('branch-l-1-0', 'uid-a', -140),
      branch('branch-l-1-1', 'uid-new', -20),
      branch('branch-l-1-2', 'uid-b', 48),
      branch('branch-r-1-0', 'uid-r0', -106),
      branch('branch-r-1-1', 'uid-r1', 14),
    ]

    const next = applyMindMapSideAnchorYPreserve(nodes, 'uid-a', -106)
    const left0 = next.find((n) => n.id === 'branch-l-1-0')
    const leftNew = next.find((n) => n.id === 'branch-l-1-1')
    const leftB = next.find((n) => n.id === 'branch-l-1-2')
    const right0 = next.find((n) => n.id === 'branch-r-1-0')
    const topic = next.find((n) => n.id === 'topic')

    expect(left0?.position?.y).toBeCloseTo(-106, 5)
    expect(leftNew?.position?.y).toBeCloseTo(14, 5)
    expect(leftB?.position?.y).toBeCloseTo(82, 5)
    expect(right0?.position?.y).toBe(-106)
    expect(topic?.position?.y).toBe(100)
  })

  it('is a no-op when the uid is missing', () => {
    const nodes: DiagramNode[] = [branch('branch-l-1-0', 'uid-a', 10)]
    expect(applyMindMapSideAnchorYPreserve(nodes, 'missing', 0)).toBe(nodes)
  })
})

describe('applyMindMapTopicYPreserve', () => {
  it('restores topic top Y without moving branches', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic', position: { x: 0, y: 40 } },
      {
        id: 'branch-l-1-0',
        text: 'A',
        type: 'branch',
        position: { x: 0, y: -106 },
        data: { [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a' },
      },
    ]
    const next = applyMindMapTopicYPreserve(nodes, -20)
    expect(next.find((n) => n.id === 'topic')?.position?.y).toBeCloseTo(-20, 5)
    expect(next.find((n) => n.id === 'branch-l-1-0')?.position?.y).toBe(-106)
  })
})

describe('applyMindMapIncrementalSiblingYPreserve', () => {
  it('pins both the anchor side and the topic', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic', position: { x: 0, y: 40 } },
      {
        id: 'branch-l-1-0',
        text: 'A',
        type: 'branch',
        position: { x: 0, y: -140 },
        data: { [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a' },
      },
      {
        id: 'branch-l-1-1',
        text: 'B',
        type: 'branch',
        position: { x: 0, y: -20 },
        data: { [MINDMAP_NODE_UID_DATA_KEY]: 'uid-new' },
      },
    ]
    const next = applyMindMapIncrementalSiblingYPreserve(nodes, {
      anchorUid: 'uid-a',
      anchorY: -106,
      topicY: -20,
    })
    expect(next.find((n) => n.id === 'branch-l-1-0')?.position?.y).toBeCloseTo(-106, 5)
    expect(next.find((n) => n.id === 'branch-l-1-1')?.position?.y).toBeCloseTo(14, 5)
    expect(next.find((n) => n.id === 'topic')?.position?.y).toBeCloseTo(-20, 5)
  })
})

describe('applyMindMapIncrementalTopLevelSiblingLayout', () => {
  it('keeps parent L1 put, places new below subtree, shifts lower L1 only', () => {
    const before: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic', position: { x: 400, y: -20 } },
      {
        id: 'branch-l-1-0',
        text: 'A',
        type: 'branch',
        position: { x: 100, y: -100 },
        data: {
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a',
          estimatedHeight: 40,
        },
      },
      {
        id: 'branch-l-2-1',
        text: 'A1',
        type: 'branch',
        position: { x: 40, y: -120 },
        data: {
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a0',
          estimatedHeight: 40,
        },
      },
      {
        id: 'branch-l-2-2',
        text: 'A2',
        type: 'branch',
        position: { x: 40, y: -60 },
        data: {
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a1',
          estimatedHeight: 40,
        },
      },
      {
        id: 'branch-l-1-3',
        text: 'B',
        type: 'branch',
        position: { x: 100, y: 40 },
        data: {
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-b',
          estimatedHeight: 40,
        },
      },
    ]
    const after: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic', position: { x: 400, y: 10 } },
      {
        id: 'branch-l-1-0',
        text: 'A',
        type: 'branch',
        position: { x: 100, y: -180 },
        data: {
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a',
          estimatedHeight: 40,
        },
      },
      {
        id: 'branch-l-2-1',
        text: 'A1',
        type: 'branch',
        position: { x: 40, y: -200 },
        data: {
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a0',
          estimatedHeight: 40,
        },
      },
      {
        id: 'branch-l-2-2',
        text: 'A2',
        type: 'branch',
        position: { x: 40, y: -140 },
        data: {
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a1',
          estimatedHeight: 40,
        },
      },
      {
        id: 'branch-l-1-1',
        text: 'New',
        type: 'branch',
        position: { x: 100, y: -40 },
        data: {
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-new',
          estimatedHeight: 40,
        },
      },
      {
        id: 'branch-l-1-2',
        text: 'B',
        type: 'branch',
        position: { x: 100, y: 40 },
        data: {
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-b',
          estimatedHeight: 40,
        },
      },
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-l-1-0' },
      { id: 'c1', source: 'branch-l-1-0', target: 'branch-l-2-1' },
      { id: 'c2', source: 'branch-l-1-0', target: 'branch-l-2-2' },
      { id: 'c3', source: 'topic', target: 'branch-l-1-1' },
      { id: 'c4', source: 'topic', target: 'branch-l-1-2' },
    ]

    const next = applyMindMapIncrementalTopLevelSiblingLayout(before, after, connections, {
      anchorUid: 'uid-a',
      newSiblingUid: 'uid-new',
      insert: 'below',
      topicY: -20,
      crossBranchGap: 28,
    })

    expect(next.find((n) => n.id === 'topic')?.position?.y).toBeCloseTo(-20, 5)
    // Place/shift then side-pack center on topic (DEFAULT_NODE_HEIGHT=50 → center 5).
    // Pre-center L1 tops -100 / 8 / 108 → anchors -80/28/128 mid 24 → delta -19.
    expect(next.find((n) => n.id === 'branch-l-1-0')?.position?.y).toBeCloseTo(-119, 5)
    expect(next.find((n) => n.id === 'branch-l-2-1')?.position?.y).toBeCloseTo(-139, 5)
    expect(next.find((n) => n.id === 'branch-l-1-1')?.position?.y).toBeCloseTo(-11, 5)
    expect(next.find((n) => n.id === 'branch-l-1-2')?.position?.y).toBeCloseTo(89, 5)
    // Enter gaps preserved under the rigid pack slide.
    expect(
      (next.find((n) => n.id === 'branch-l-1-1')?.position?.y ?? 0) -
        (next.find((n) => n.id === 'branch-l-1-0')?.position?.y ?? 0)
    ).toBeCloseTo(108, 5)
  })
})
