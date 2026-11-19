import { describe, expect, it } from 'vitest'

import type { DiagramNode } from '@/types'
import {
  formatDoubleBubbleWorksheetTopic,
  readDoubleBubbleTopicPair,
} from '@/utils/doubleBubbleWorksheetTopic'

describe('doubleBubbleWorksheetTopic', () => {
  const nodes: DiagramNode[] = [
    { id: 'left-topic', text: '主题A', type: 'topic', position: { x: 0, y: 0 } },
    { id: 'right-topic', text: '主题B', type: 'topic', position: { x: 100, y: 0 } },
  ]

  it('reads left and right topic texts', () => {
    expect(readDoubleBubbleTopicPair(nodes)).toEqual({ left: '主题A', right: '主题B' })
  })

  it('formats the worksheet compare line', () => {
    expect(
      formatDoubleBubbleWorksheetTopic(nodes, (left, right) => `对比"${left}"与"${right}"`)
    ).toBe('对比"主题A"与"主题B"')
  })

  it('falls back to a single side when the other is empty', () => {
    expect(
      formatDoubleBubbleWorksheetTopic(
        [{ id: 'left-topic', text: '猫', type: 'topic', position: { x: 0, y: 0 } }],
        (left, right) => `对比"${left}"与"${right}"`
      )
    ).toBe('猫')
  })
})
