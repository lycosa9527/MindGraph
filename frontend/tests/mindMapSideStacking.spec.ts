import { describe, expect, it } from 'vitest'

import { DEFAULT_MINDMAP_BRANCH_GAP } from '@/composables/diagrams/layoutConfig'
import type { DiagramNode } from '@/types'
import { MINDMAP_NODE_UID_DATA_KEY } from '@/utils/mindMapNodeUid'
import {
  applyMindMapSideAnchorYPreserve,
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
    expect(centered[1]! - (centered[0]! + spans[0]!)).toBe(gap)
  })

  it('keeps the cross-branch gap when two roots have unequal spans', () => {
    const spans = [144, 92]
    const tops = computeSymmetricRootStartYs(spans, topic, gap)
    expect(tops[1]! - (tops[0]! + spans[0]!)).toBe(gap)
  })

  it('packs three roots sequentially around the topic', () => {
    const spans = [92, 40, 92]
    const tops = computeSymmetricRootStartYs(spans, topic, gap)
    expect(tops).toHaveLength(3)
    expect(tops[1]! - (tops[0]! + spans[0]!)).toBe(gap)
    expect(tops[2]! - (tops[1]! + spans[1]!)).toBe(gap)
    const total = spans.reduce((a, b) => a + b, 0) + 2 * gap
    expect(tops[0]).toBeCloseTo(topic - total / 2, 5)
  })
})

describe('applyMindMapSideAnchorYPreserve', () => {
  function branch(
    id: string,
    uid: string,
    y: number
  ): DiagramNode {
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
