import { describe, expect, it } from 'vitest'

import { recalculateCircleMapLayout } from '@/stores/specLoader/circleMap'
import { estimateContextCircleDiameter } from '@/stores/specLoader/utils'
import type { DiagramNode } from '@/types'

describe('thinking map typography layout — circle map', () => {
  it('estimates larger context circles when font size and weight increase', () => {
    const text = '认知资源不足'
    const base = estimateContextCircleDiameter(text)
    const enlarged = estimateContextCircleDiameter(text, undefined, {
      fontSize: 24,
      fontWeight: 'bold',
    })
    expect(enlarged).toBeGreaterThan(base)
  })

  it('expands ring spacing when a context node uses a larger bold label', () => {
    const topic: DiagramNode = { id: 'topic', text: '焦虑', type: 'center' }
    const contexts: DiagramNode[] = Array.from({ length: 8 }, (_, index) => ({
      id: `context-${index}`,
      text: index === 1 ? '认知资源不足' : '联想',
      type: 'bubble',
      data: { groupIndex: index },
    }))
    const plain = recalculateCircleMapLayout([topic, ...contexts])
    const formatted = recalculateCircleMapLayout([
      topic,
      ...contexts.map((node, index) =>
        index === 1
          ? {
              ...node,
              style: { fontSize: 22, fontWeight: 'bold' as const, textDecoration: 'underline' },
            }
          : node
      ),
    ])
    const plainContext = plain.find((node) => node.id === 'context-1')
    const formattedContext = formatted.find((node) => node.id === 'context-1')
    expect(formattedContext?.style?.size ?? 0).toBeGreaterThan(plainContext?.style?.size ?? 0)
    const plainPos = plainContext?.position
    const formattedPos = formattedContext?.position
    if (plainPos && formattedPos) {
      const plainDist = Math.hypot(plainPos.x - 400, plainPos.y - 300)
      const formattedDist = Math.hypot(formattedPos.x - 400, formattedPos.y - 300)
      expect(formattedDist).toBeGreaterThanOrEqual(plainDist)
    }
  })
})
