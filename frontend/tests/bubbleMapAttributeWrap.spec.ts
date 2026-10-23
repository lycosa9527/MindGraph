import { describe, expect, it } from 'vitest'

import { loadBubbleMapSpec, recalculateBubbleMapLayout } from '@/stores/specLoader/bubbleMap'
import { CONTEXT_FONT_SIZE, calculateBubbleMapRadius } from '@/stores/specLoader/textMeasurement'
import type { DiagramNode } from '@/types'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

function attributeSize(nodes: DiagramNode[]): number {
  const bubble = nodes.find((node) => node.type === 'bubble')
  return bubble?.style?.size ?? 0
}

describe('bubble map attribute wrap', () => {
  it('keeps a short auto-complete answer on one line and omits noWrap', () => {
    const loaded = loadBubbleMapSpec({ topic: '苹果', attributes: ['甜'] })
    const bubble = loaded.nodes.find((node) => node.type === 'bubble')
    expect(bubble?.style?.noWrap).toBeUndefined()
    const singleLine = calculateBubbleMapRadius(
      '甜',
      CONTEXT_FONT_SIZE,
      10,
      35,
      false,
      false,
      DIAGRAM_NODE_FONT_STACK
    )
    expect(attributeSize(loaded.nodes)).toBeGreaterThanOrEqual(singleLine * 2)
  })

  it('keeps a phrase that fits the mind-map column on one line', () => {
    const phrase = '香甜多汁的红色果实'
    const loaded = loadBubbleMapSpec({ topic: '苹果', attributes: [phrase] })
    const singleLine =
      calculateBubbleMapRadius(
        phrase,
        CONTEXT_FONT_SIZE,
        10,
        35,
        false,
        false,
        DIAGRAM_NODE_FONT_STACK
      ) * 2
    expect(attributeSize(loaded.nodes)).toBeGreaterThanOrEqual(singleLine)
  })

  it('wraps a long auto-complete answer instead of growing to the full line', () => {
    const long = '香甜多汁的红色果实'.repeat(4)
    const loaded = loadBubbleMapSpec({ topic: '苹果', attributes: ['甜', long] })
    const bubbles = loaded.nodes.filter((node) => node.type === 'bubble')
    expect(bubbles.every((node) => node.style?.noWrap == null)).toBe(true)
    const wrapped = bubbles[0]?.style?.size ?? 0
    const shortOnly = attributeSize(loadBubbleMapSpec({ topic: '苹果', attributes: ['甜'] }).nodes)
    const fullLine =
      calculateBubbleMapRadius(
        long,
        CONTEXT_FONT_SIZE,
        10,
        35,
        false,
        false,
        DIAGRAM_NODE_FONT_STACK
      ) * 2
    expect(wrapped).toBeGreaterThan(shortOnly)
    expect(wrapped).toBeLessThan(fullLine)
    expect(bubbles[0]?.style?.size).toBe(bubbles[1]?.style?.size)
  })

  it('drops a stored noWrap flag when the map is laid out again', () => {
    const long = '香甜多汁的红色果实'.repeat(4)
    const topic: DiagramNode = { id: 'topic', text: '苹果', type: 'topic' }
    const bubble: DiagramNode = {
      id: 'bubble-0',
      text: long,
      type: 'bubble',
      data: { groupIndex: 0 },
      style: { noWrap: true, fontSize: CONTEXT_FONT_SIZE },
    }
    const laid = recalculateBubbleMapLayout([topic, bubble])
    const next = laid.find((node) => node.id === 'bubble-0')
    expect(next?.style?.noWrap).toBeUndefined()
    const fullLine =
      calculateBubbleMapRadius(
        long,
        CONTEXT_FONT_SIZE,
        10,
        35,
        false,
        false,
        DIAGRAM_NODE_FONT_STACK
      ) * 2
    expect(next?.style?.size ?? 0).toBeLessThan(fullLine)
  })

  it('sizes an emoji adornment the same as those characters in the label', () => {
    const topic: DiagramNode = { id: 'topic', text: '主题', type: 'topic' }
    const labeled: DiagramNode = {
      id: 'bubble-0',
      text: '属性5',
      type: 'bubble',
      data: { groupIndex: 0 },
    }
    const other: DiagramNode = {
      id: 'bubble-1',
      text: '124',
      type: 'bubble',
      data: { groupIndex: 1 },
    }
    const withIcon = recalculateBubbleMapLayout(
      [topic, labeled, other],
      {},
      {
        'bubble-0': { icon: '😬' },
      }
    )
    const asText = recalculateBubbleMapLayout([topic, { ...labeled, text: '😬 属性5' }, other])
    const size = (nodes: DiagramNode[], id: string): number =>
      nodes.find((node) => node.id === id)?.style?.size ?? 0
    expect(size(withIcon, 'bubble-0')).toBe(size(asText, 'bubble-0'))
    expect(size(withIcon, 'topic')).toBe(size(asText, 'topic'))
  })

  it('still counts the emoji as text when a picture is also set', () => {
    const topic: DiagramNode = { id: 'topic', text: '主题', type: 'topic' }
    const bubble: DiagramNode = {
      id: 'bubble-0',
      text: '属性5',
      type: 'bubble',
      data: { groupIndex: 0 },
    }
    const withImage = recalculateBubbleMapLayout(
      [topic, bubble],
      {},
      {
        'bubble-0': { icon: '😬', imageUrl: 'data:image/png;base64,aa' },
      }
    )
    const asText = recalculateBubbleMapLayout([topic, { ...bubble, text: '😬 属性5' }])
    const size = (nodes: DiagramNode[]): number =>
      nodes.find((node) => node.id === 'bubble-0')?.style?.size ?? 0
    expect(size(withImage)).toBe(size(asText))
  })
})
