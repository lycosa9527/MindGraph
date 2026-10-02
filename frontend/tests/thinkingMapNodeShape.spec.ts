import { describe, expect, it } from 'vitest'

import { bridgePairVerticalGap } from '@/stores/specLoader/bridgeMap'
import { recalculateBubbleMapLayout } from '@/stores/specLoader/bubbleMap'
import type { DiagramNode } from '@/types'
import {
  CIRCLE_MAP_OVAL_WIDTH_RATIO,
  defaultDisplayedNodeShape,
  shapePackHalfExtent,
  shapeRayHitDistance,
} from '@/utils/nodeShapeStyle'

describe('thinking map node shape outline', () => {
  it('keeps an unset shape and an oval square on the circle extent', () => {
    expect(shapePackHalfExtent(undefined, 40, 40)).toBe(40)
    expect(shapePackHalfExtent('oval', 40, 40)).toBe(40)
  })

  it('packs rectangle and rounded squares by the box diagonal', () => {
    expect(shapePackHalfExtent('rectangle', 40, 40)).toBeCloseTo(40 * Math.SQRT2)
    expect(shapePackHalfExtent('rounded', 40, 40)).toBeCloseTo(40 * Math.SQRT2)
    expect(shapePackHalfExtent('underline', 30, 12)).toBeCloseTo(Math.hypot(30, 12))
  })

  it('packs a wide oval on its long axis and stops the line on that outline', () => {
    expect(shapePackHalfExtent('oval', 60, 40)).toBe(60)
    expect(shapeRayHitDistance('oval', 60, 40, 1, 0)).toBeCloseTo(60)
    expect(shapeRayHitDistance('oval', 60, 40, 0, 1)).toBeCloseTo(40)
    const diagonal = Math.SQRT1_2
    const boxHit = Math.min(60 / diagonal, 40 / diagonal)
    expect(shapeRayHitDistance('oval', 60, 40, diagonal, diagonal)).toBeLessThan(boxHit)
  })

  it('opens a bubble ring when a disk becomes an oval and keeps the disk height', () => {
    const topic: DiagramNode = { id: 'topic', text: '主题', type: 'topic' }
    const bubbles: DiagramNode[] = Array.from({ length: 6 }, (_, index) => ({
      id: `bubble-${index}`,
      text: '属性',
      type: 'bubble',
      data: { groupIndex: index },
    }))
    const round = recalculateBubbleMapLayout([topic, ...bubbles])
    const oval = recalculateBubbleMapLayout([
      { ...topic, style: { nodeShape: 'oval' } },
      ...bubbles.map((node) => ({ ...node, style: { nodeShape: 'oval' as const } })),
    ])
    const roundTopic = round.find((node) => node.id === 'topic')
    const ovalTopic = oval.find((node) => node.id === 'topic')
    expect(ovalTopic?.style?.size).toBe(roundTopic?.style?.size)
    const topicR = (roundTopic?.style?.size ?? 0) / 2
    expect(ovalTopic?.position?.x).toBe(
      Math.round((roundTopic?.position?.x ?? 0) + topicR - topicR * CIRCLE_MAP_OVAL_WIDTH_RATIO)
    )
    expect(ovalTopic?.position?.y).toBe(roundTopic?.position?.y)
  })

  it('stops a radial line on the circle and on the rectangle', () => {
    expect(shapeRayHitDistance(undefined, 40, 40, 1, 0)).toBe(40)
    expect(shapeRayHitDistance('oval', 40, 40, 0, 1)).toBe(40)
    expect(shapeRayHitDistance('rectangle', 40, 40, 1, 0)).toBe(40)
    const diagonal = Math.SQRT1_2
    expect(shapeRayHitDistance('oval', 40, 40, diagonal, diagonal)).toBe(40)
    expect(shapeRayHitDistance('rectangle', 40, 40, diagonal, diagonal)).toBeCloseTo(
      40 * Math.SQRT2
    )
  })

  it('keeps the bridge gap at 5px until a pair word has a shape', () => {
    expect(bridgePairVerticalGap([])).toBe(5)
    const label: DiagramNode = { id: 'dimension-label', text: 'as', type: 'label' }
    expect(bridgePairVerticalGap([label])).toBe(5)
    const pair: DiagramNode = {
      id: 'pair-a',
      text: 'hot',
      type: 'branch',
      data: { pairIndex: 0, position: 'left' },
      style: { nodeShape: 'rectangle' },
    }
    expect(bridgePairVerticalGap([pair])).toBe(16)
  })

  it('highlights the shape a node already shows', () => {
    expect(defaultDisplayedNodeShape('double_bubble_map', 'topic')).toBe('oval')
    expect(defaultDisplayedNodeShape('double_bubble_map', 'bubble')).toBe('oval')
    expect(defaultDisplayedNodeShape('circle_map', 'center')).toBe('oval')
    expect(defaultDisplayedNodeShape('bubble_map', 'bubble')).toBe('oval')
    expect(defaultDisplayedNodeShape('flow_map', 'flow')).toBe('oval')
    expect(defaultDisplayedNodeShape('flow_map', 'flowSubstep')).toBe('oval')
    expect(defaultDisplayedNodeShape('multi_flow_map', 'topic')).toBe('oval')
    expect(defaultDisplayedNodeShape('brace_map', 'brace')).toBe('oval')
    expect(defaultDisplayedNodeShape('concept_map', 'concept')).toBe('oval')
    expect(defaultDisplayedNodeShape('tree_map', 'topic')).toBe('oval')
    expect(defaultDisplayedNodeShape('tree_map', 'branch')).toBe('rounded')
    expect(defaultDisplayedNodeShape('bridge_map', 'branch')).toBeNull()
  })
})
