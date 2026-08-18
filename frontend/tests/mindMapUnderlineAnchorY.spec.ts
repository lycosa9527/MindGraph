import { describe, expect, it } from 'vitest'

import {
  mindMapConnectionAnchorY,
  resolveMindMapTopicLayoutWidth,
  resolveMindMapTopicStemWidth,
} from '@/config/mindMapGeometry'
import { resolveMindMapEdgeEndpoint } from '@/utils/mindMapEdgeEndpoints'

describe('resolveMindMapTopicLayoutWidth', () => {
  it('uses estimate when measured is missing', () => {
    expect(resolveMindMapTopicLayoutWidth(null, 120)).toBe(120)
    expect(resolveMindMapTopicLayoutWidth(undefined, 120)).toBe(120)
    expect(resolveMindMapTopicLayoutWidth(0, 120)).toBe(120)
  })

  it('never shrinks below estimate (matches layout column width)', () => {
    expect(resolveMindMapTopicLayoutWidth(90, 120)).toBe(120)
    expect(resolveMindMapTopicLayoutWidth(140, 120)).toBe(140)
  })
})

describe('resolveMindMapTopicStemWidth', () => {
  it('uses estimate when measured is missing', () => {
    expect(resolveMindMapTopicStemWidth(null, 120)).toBe(120)
    expect(resolveMindMapTopicStemWidth(0, 120)).toBe(120)
  })

  it('uses painted measured width so the right stem meets the topic box', () => {
    expect(resolveMindMapTopicStemWidth(90, 120)).toBe(90)
    expect(resolveMindMapTopicStemWidth(140, 120)).toBe(140)
  })
})

describe('resolveMindMapEdgeEndpoint underline Y', () => {
  const node = {
    id: 'branch-r-2-1',
    position: { x: 644.5, y: 209.5 },
    data: { style: { nodeShape: 'underline' as const } },
  }
  const measured = { width: 90, height: 29 }
  // Bar midline: top + height - stroke/2 = 209.5 + 29 - 1.
  const barMidline = mindMapConnectionAnchorY(node.position.y, measured.height, 'underline')

  it('anchors to the deterministic bar midline (matches layout + DOM bar)', () => {
    expect(barMidline).toBe(237.5)
  })

  it('ignores the vue-flow handle Y and uses the bar midline', () => {
    const resolved = resolveMindMapEdgeEndpoint(
      node,
      'target',
      { x: 644.5, y: 240 },
      node.data?.style,
      measured
    )
    expect(resolved.y).toBe(barMidline)
  })

  it('does not drift to a stale/low fallback Y', () => {
    const resolved = resolveMindMapEdgeEndpoint(
      node,
      'target',
      { x: 644.5, y: 209.5 },
      node.data?.style,
      measured
    )
    expect(resolved.y).toBe(barMidline)
  })

  it('joins exactly at the side edge (right-side child = left edge, no overlap)', () => {
    const resolved = resolveMindMapEdgeEndpoint(
      node,
      'target',
      { x: 644.5, y: 240 },
      node.data?.style,
      measured
    )
    // Right-side child target joins the left edge (position.x = 644.5), flush with the bar.
    expect(resolved.x).toBe(644.5)
  })

  it('joins exactly at the side edge for a left-side child (right edge, no overlap)', () => {
    const leftNode = {
      id: 'branch-l-2-1',
      position: { x: 100, y: 209.5 },
      data: { style: { nodeShape: 'underline' as const } },
    }
    const resolved = resolveMindMapEdgeEndpoint(
      leftNode,
      'target',
      { x: 100, y: 240 },
      leftNode.data?.style,
      measured
    )
    // Left-side child target joins the right edge (position.x + width = 190), flush with the bar.
    expect(resolved.x).toBe(190)
  })
})

describe('resolveMindMapEdgeEndpoint rounded L1 branch exits', () => {
  const measured = { width: 100, height: 40 }

  it('right L1 source uses outer (right) edge, ignoring inward VF handle X', () => {
    const node = {
      id: 'branch-r-1-0',
      position: { x: 520, y: 200 },
      data: { style: { nodeShape: 'rounded' as const } },
    }
    // Vue Flow often reports the inward target-handle X after layout remap.
    const resolved = resolveMindMapEdgeEndpoint(
      node,
      'source',
      { x: 520, y: 250 },
      node.data.style,
      measured,
      'classic'
    )
    expect(resolved.x).toBe(620)
    expect(resolved.y).toBe(mindMapConnectionAnchorY(200, 40, 'rounded'))
  })

  it('left L1 source uses outer (left) edge, ignoring inward VF handle X', () => {
    const node = {
      id: 'branch-l-1-0',
      position: { x: 200, y: 200 },
      data: { style: { nodeShape: 'rounded' as const } },
    }
    const resolved = resolveMindMapEdgeEndpoint(
      node,
      'source',
      { x: 300, y: 250 },
      node.data.style,
      measured,
      'classic'
    )
    expect(resolved.x).toBe(200)
    expect(resolved.y).toBe(mindMapConnectionAnchorY(200, 40, 'rounded'))
  })

  it('UUID L1 with stamped side uses the box edge, not the vue-flow handle', () => {
    const node = {
      id: 'uid-l1',
      position: { x: 520, y: 200 },
      data: {
        mindMapSide: 'right' as const,
        style: { nodeShape: 'rounded' as const },
      },
    }
    const resolved = resolveMindMapEdgeEndpoint(
      node,
      'source',
      { x: 520, y: 250 },
      node.data.style,
      measured,
      'classic'
    )
    expect(resolved.x).toBe(620)
    expect(resolved.y).toBe(mindMapConnectionAnchorY(200, 40, 'rounded'))
  })

  it('right L1 target uses inner (left) edge for topic→L1', () => {
    const node = {
      id: 'branch-r-1-0',
      position: { x: 520, y: 200 },
      data: { style: { nodeShape: 'rounded' as const } },
    }
    const resolved = resolveMindMapEdgeEndpoint(
      node,
      'target',
      { x: 999, y: 999 },
      node.data.style,
      measured,
      'classic'
    )
    expect(resolved.x).toBe(520)
  })
})
