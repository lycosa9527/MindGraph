import { describe, expect, it } from 'vitest'

import type { DiagramNode } from '@/types'
import { stampDoubleBubbleData } from '@/utils/doubleBubbleMapIdentity'
import { buildDoubleBubbleSlides } from '@/utils/doubleBubbleSlides'

function bubble(
  id: string,
  text: string,
  role?: 'similarity' | 'leftDiff' | 'rightDiff',
  index = 0
): DiagramNode {
  return {
    id,
    text,
    type: 'topic',
    position: { x: 0, y: 0 },
    data: role ? stampDoubleBubbleData(role, index) : undefined,
  }
}

describe('buildDoubleBubbleSlides', () => {
  const nodes: DiagramNode[] = [
    bubble('left-topic', '猫'),
    bubble('right-topic', '狗'),
    bubble('sim-a', '宠物', 'similarity', 0),
    bubble('sim-b', '哺乳', 'similarity', 1),
    bubble('ld-0', '喵', 'leftDiff', 0),
    bubble('rd-0', '汪', 'rightDiff', 0),
    bubble('ld-1', '爪', 'leftDiff', 1),
  ]

  it('walks overview → both topics → each similarity → each difference pair', () => {
    const slides = buildDoubleBubbleSlides(nodes)
    expect(slides.map((slide) => slide.id)).toEqual([
      'overview',
      'left-topic',
      'right-topic',
      'sim-a',
      'sim-b',
      'diff-pair-0',
      'diff-pair-1',
    ])
    expect(slides[0]?.title).toBe('猫 / 狗')
    expect(slides.find((slide) => slide.id === 'diff-pair-0')?.focusNodeIds).toEqual([
      'ld-0',
      'rd-0',
    ])
    expect(slides.find((slide) => slide.id === 'diff-pair-0')?.title).toBe('喵 / 汪')
    expect(slides.find((slide) => slide.id === 'diff-pair-1')?.focusNodeIds).toEqual(['ld-1'])
  })

  it('returns empty for empty node list', () => {
    expect(buildDoubleBubbleSlides([])).toEqual([])
  })
})
