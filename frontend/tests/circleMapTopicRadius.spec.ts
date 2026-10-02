import { describe, expect, it } from 'vitest'

import { DEFAULT_CENTER_X, DEFAULT_CENTER_Y } from '@/composables/diagrams/layoutConfig'
import { recalculateCircleMapLayout } from '@/stores/specLoader/circleMap'
import { calculateCircleMapLayout } from '@/stores/specLoader/utils'
import type { DiagramNode } from '@/types'
import { CIRCLE_MAP_OVAL_WIDTH_RATIO } from '@/utils/nodeShapeStyle'

describe('circle map default topic radius', () => {
  it('uses text-based floor for short default labels without DOM overrides', () => {
    const layout = calculateCircleMapLayout(8, ['Context 1', 'Context 2'], 'Topic')
    expect(layout.topicR).toBe(60)
  })

  it('does not grow topic when DOM override matches short plain text', () => {
    const layout = calculateCircleMapLayout(8, ['Context 1'], 'Topic', {
      topicR: 45,
    })
    expect(layout.topicR).toBe(60)
  })

  it('grows the ring for a rectangle context and keeps an oval square on the circle', () => {
    const plain = calculateCircleMapLayout(8, ['Context 1', 'Context 2'], 'Topic')
    const oval = calculateCircleMapLayout(8, ['Context 1', 'Context 2'], 'Topic', {
      contextPackR: plain.uniformContextR,
      topicPackR: plain.topicR,
    })
    expect(oval.childrenRadius).toBe(plain.childrenRadius)
    expect(oval.outerCircleR).toBe(plain.outerCircleR)
    expect(oval.uniformContextR).toBe(plain.uniformContextR)

    const boxed = calculateCircleMapLayout(8, ['Context 1', 'Context 2'], 'Topic', {
      contextPackR: plain.uniformContextR * Math.SQRT2,
      topicPackR: plain.topicR,
    })
    expect(boxed.uniformContextR).toBe(plain.uniformContextR)
    expect(boxed.childrenRadius).toBeGreaterThan(plain.childrenRadius)
    expect(boxed.outerCircleR).toBeGreaterThan(plain.outerCircleR)
  })

  it('draws a circle-map oval wider than the disk and keeps that height', () => {
    const topic: DiagramNode = { id: 'topic', text: '主题', type: 'center' }
    const contexts: DiagramNode[] = Array.from({ length: 8 }, (_, index) => ({
      id: `context-${index}`,
      text: '联想',
      type: 'bubble',
      data: { groupIndex: index },
    }))
    const round = recalculateCircleMapLayout([topic, ...contexts])
    const oval = recalculateCircleMapLayout([
      { ...topic, style: { nodeShape: 'oval' } },
      ...contexts.map((node) => ({ ...node, style: { nodeShape: 'oval' as const } })),
    ])
    const roundTopic = round.find((node) => node.id === 'topic')
    const ovalTopic = oval.find((node) => node.id === 'topic')
    const roundContext = round.find((node) => node.id === 'context-0')
    const ovalContext = oval.find((node) => node.id === 'context-0')
    const topicR = (roundTopic?.style?.size ?? 0) / 2
    const contextR = (roundContext?.style?.size ?? 0) / 2

    expect(ovalTopic?.style?.size).toBe(roundTopic?.style?.size)
    expect(ovalContext?.style?.size).toBe(roundContext?.style?.size)
    expect(ovalTopic?.position).toEqual({
      x: Math.round(DEFAULT_CENTER_X - topicR * CIRCLE_MAP_OVAL_WIDTH_RATIO),
      y: Math.round(DEFAULT_CENTER_Y - topicR),
    })
    expect(ovalContext?.position?.x).not.toBe(roundContext?.position?.x)
    const roundBoundary = round.find((node) => node.type === 'boundary')
    const ovalBoundary = oval.find((node) => node.type === 'boundary')
    expect(ovalBoundary?.style?.width ?? 0).toBeGreaterThan(roundBoundary?.style?.width ?? 0)

    const measured = {
      topic: { width: topicR * 2 * CIRCLE_MAP_OVAL_WIDTH_RATIO, height: topicR * 2 },
      'context-0': { width: contextR * 2 * CIRCLE_MAP_OVAL_WIDTH_RATIO, height: contextR * 2 },
    }
    const again = recalculateCircleMapLayout(
      [
        { ...topic, style: { nodeShape: 'oval' } },
        ...contexts.map((node) => ({ ...node, style: { nodeShape: 'oval' as const } })),
      ],
      measured
    )
    expect(again.find((node) => node.id === 'topic')?.style?.size).toBe(roundTopic?.style?.size)
    expect(again.find((node) => node.id === 'context-0')?.style?.size).toBe(
      roundContext?.style?.size
    )
  })
})
