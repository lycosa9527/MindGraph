import { describe, expect, it } from 'vitest'

import { loadDoubleBubbleMapSpec } from '@/stores/specLoader/doubleBubbleMap'
import { recalculateDoubleBubbleMapLayout } from '@/stores/specLoader/doubleBubbleMapMeasuredLayout'
import {
  loadMultiFlowMapSpec,
  recalculateMultiFlowMapLayout,
} from '@/stores/specLoader/multiFlowMap'
import type { DiagramNode } from '@/types'
import { readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'
import { isMultiFlowCauseNode } from '@/utils/multiFlowMapIdentity'
import {
  NODE_IMAGE_FRAME_MIN_WIDTH,
  NODE_IMAGE_GAP,
  NODE_IMAGE_PILL_PADDING,
  NODE_IMAGE_THUMB_HEIGHT,
  releaseNodeBoxForImage,
  thinkingMapImageNodeIds,
  thinkingMapNodeHasImage,
} from '@/utils/nodeImageFrame'

function roleNodes(
  nodes: DiagramNode[],
  role: 'similarity' | 'leftDiff' | 'rightDiff'
): DiagramNode[] {
  return nodes
    .filter((node) => readDoubleBubbleRole(node) === role)
    .sort((a, b) => (a.position.y ?? 0) - (b.position.y ?? 0))
}

describe('thinking-map image frame', () => {
  it('reads an image adornment by node id', () => {
    const data = {
      _mindmap_adornments: { 'similarity-0': { imageUrl: 'data:image/png;base64,aa' } },
    }
    expect(thinkingMapNodeHasImage(data, 'similarity-0')).toBe(true)
    expect(thinkingMapImageNodeIds(data)).toEqual(new Set(['similarity-0']))
    expect(thinkingMapNodeHasImage(data, 'similarity-1')).toBe(false)
  })

  it('hugs the thumbnail instead of keeping a text pill', () => {
    const fitted = releaseNodeBoxForImage(
      {
        width: '140px',
        height: '48px',
        maxWidth: '140px',
        minWidth: '140px',
        borderRadius: '9999px',
      },
      true
    )
    expect(fitted.width).toBe('max-content')
    expect(fitted.height).toBe('max-content')
    expect(fitted.maxWidth).toBe('none')
    expect(fitted.minWidth).toBeUndefined()
    expect(fitted.minHeight).toBeUndefined()
    expect(fitted.padding).toBe(NODE_IMAGE_PILL_PADDING)
    expect(fitted.borderRadius).toBe('9999px')
    expect(fitted.overflow).toBe('visible')

    const sharp = releaseNodeBoxForImage(
      { width: '80px', padding: '9px 18px', borderRadius: '0px' },
      true
    )
    expect(sharp.borderRadius).toBe('0px')
    expect(sharp.padding).toBe('9px 18px')
    expect(releaseNodeBoxForImage({ width: '140px' }, false).width).toBe('140px')
  })
})

describe('double bubble image layout', () => {
  it('leaves text-only geometry untouched', () => {
    const { nodes } = loadDoubleBubbleMapSpec({
      left: 'Apple',
      right: 'Banana',
      similarities: ['fruit', 'sweet'],
      leftDifferences: ['red'],
      rightDifferences: ['yellow'],
    })
    expect(recalculateDoubleBubbleMapLayout(nodes, {}, new Set())).toBe(nodes)
  })

  it('stacks a taller similarity and keeps a column gap', () => {
    const { nodes } = loadDoubleBubbleMapSpec({
      left: '主题A',
      right: '主题B',
      similarities: ['相似点 1', '相似点 2'],
      leftDifferences: ['差异A'],
      rightDifferences: ['差异B'],
    })
    const sims = roleNodes(nodes, 'similarity')
    const first = sims[0]
    expect(first).toBeDefined()
    const imageHeight = 168
    const placed = recalculateDoubleBubbleMapLayout(
      nodes,
      { [first.id]: { width: 200, height: imageHeight } },
      new Set([first.id])
    )
    const placedSims = roleNodes(placed, 'similarity')
    const top = placedSims[0]
    const below = placedSims[1]
    expect(top?.id).toBe(first.id)
    expect((below?.position.y ?? 0) >= (top?.position.y ?? 0) + imageHeight).toBe(true)

    const leftTopic = placed.find((node) => node.id === 'left-topic')
    const topicRight =
      (leftTopic?.position.x ?? 0) + (leftTopic?.style?.size ?? leftTopic?.style?.width ?? 0)
    expect(top?.position.x ?? 0).toBeGreaterThanOrEqual(topicRight)
  })

  it('reserves the image frame before the picture has been measured', () => {
    const { nodes } = loadDoubleBubbleMapSpec({
      left: 'A',
      right: 'B',
      similarities: ['one', 'two'],
      leftDifferences: [],
      rightDifferences: [],
    })
    const first = roleNodes(nodes, 'similarity')[0]
    const textHeight = first?.style?.height ?? 0
    const placed = recalculateDoubleBubbleMapLayout(nodes, {}, new Set([first?.id ?? '']))
    const placedSims = roleNodes(placed, 'similarity')
    const gap = (placedSims[1]?.position.y ?? 0) - (placedSims[0]?.position.y ?? 0)
    expect(gap).toBeGreaterThanOrEqual(textHeight + NODE_IMAGE_THUMB_HEIGHT + NODE_IMAGE_GAP)
  })
})

describe('multi-flow image layout', () => {
  it('widens the cause column to the measured image', () => {
    const loaded = loadMultiFlowMapSpec({
      event: '研讨',
      causes: ['图片', '文字'],
      effects: ['结果'],
    })
    const cause = loaded.nodes.find((node) => isMultiFlowCauseNode(node))
    expect(cause).toBeDefined()
    const nodes = recalculateMultiFlowMapLayout(
      loaded.nodes,
      null,
      {},
      { [cause?.id ?? '']: { width: 240, height: 160 } },
      new Set([cause?.id ?? ''])
    )
    const placed = nodes.find((node) => node.id === cause?.id)
    const event = nodes.find((node) => node.id === 'event')
    const width = typeof placed?.style?.width === 'number' ? placed.style.width : 0
    expect(width).toBeGreaterThanOrEqual(240)
    expect(width).toBeGreaterThanOrEqual(NODE_IMAGE_FRAME_MIN_WIDTH)
    expect((placed?.position.x ?? 0) + width).toBeLessThanOrEqual(event?.position.x ?? 0)
  })
})
