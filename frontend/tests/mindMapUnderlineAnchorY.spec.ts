import { describe, expect, it } from 'vitest'

import { mindMapConnectionAnchorY } from '@/config/mindMapGeometry'
import { resolveMindMapEdgeEndpoint } from '@/utils/mindMapEdgeEndpoints'

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
