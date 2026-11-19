import { describe, expect, it } from 'vitest'

import {
  clockwiseFromTop,
  doubleBubbleRevealOrder,
  linesBetweenShown,
} from '@/composables/training/glassesPlay'
import { mindGlassDemoSteps } from '@/composables/training/mindGlassDemo'

describe('glasses play', () => {
  it('orders bubbles clockwise from the top', () => {
    const center = { id: 'topic', x: 0, y: 0 }
    const order = clockwiseFromTop(
      [
        { id: 'east', x: 10, y: 0 },
        { id: 'north', x: 0, y: -10 },
        { id: 'west', x: -10, y: 0 },
        { id: 'south', x: 0, y: 10 },
      ],
      center
    )
    expect(order).toEqual(['north', 'east', 'south', 'west'])
  })

  it('draws a line only after both of its nodes are showing', () => {
    const links = [
      { id: 'topic-a', source: 'topic', target: 'a' },
      { id: 'topic-b', source: 'topic', target: 'b' },
    ]
    expect(linesBetweenShown(links, new Set(['topic']))).toEqual([])
    expect(linesBetweenShown(links, new Set(['topic', 'a']))).toEqual(['topic-a'])
  })

  it('stages a double bubble as topics, then shared nodes, then differences', () => {
    const order = doubleBubbleRevealOrder([
      { id: 'right-1', role: 'rightDiff', index: 0 },
      { id: 'share-b', role: 'similarity', index: 1 },
      { id: 'left-0', role: 'leftDiff', index: 0 },
      { id: 'share-a', role: 'similarity', index: 0 },
      { id: 'left-1', role: 'leftDiff', index: 1 },
    ])
    expect(order.similarities).toEqual(['share-a', 'share-b'])
    expect(order.differences).toEqual(['left-0', 'right-1', 'left-1'])
  })

  it('builds the three demo slides', () => {
    const steps = mindGlassDemoSteps(4)
    expect(steps.map((step) => step.glasses_reveal)).toEqual(['', 'clockwise', 'stages'])
    expect(steps[0]?.glasses_line).toContain('Welcome to MindGlass demo')
    expect(steps[1]?.diagram_type).toBe('bubble_map')
    const attributes = steps[1]?.diagram_spec?.attributes
    expect(Array.isArray(attributes) ? attributes.length : 0).toBe(8)
    expect(steps[2]?.diagram_type).toBe('double_bubble_map')
    expect(steps[2]?.position).toBe(6)
  })
})
