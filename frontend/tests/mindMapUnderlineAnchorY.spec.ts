import { describe, expect, it } from 'vitest'

import {
  mindMapConnectionAnchorY,
  mindMapUnderlineHandleAnchorY,
} from '@/config/mindMapGeometry'
import { resolveMindMapEdgeEndpoint } from '@/utils/mindMapEdgeEndpoints'

describe('mindMapUnderlineHandleAnchorY', () => {
  it('places handle center below box-bottom formula (matches domHandle probe)', () => {
    const top = 209.5
    const height = 29
    const formula = mindMapConnectionAnchorY(top, height, 'underline')
    const handle = mindMapUnderlineHandleAnchorY(top, height)
    expect(formula).toBe(237.5)
    expect(handle).toBe(240.5)
  })
})

describe('resolveMindMapEdgeEndpoint underline Y', () => {
  const node = {
    id: 'branch-r-2-1',
    position: { x: 644.5, y: 209.5 },
    data: { style: { nodeShape: 'underline' as const } },
  }

  it('uses vue-flow handle Y when provided', () => {
    const resolved = resolveMindMapEdgeEndpoint(
      node,
      'target',
      { x: 644.5, y: 240 },
      node.data?.style,
      { width: 90, height: 29 }
    )
    expect(resolved.y).toBe(240)
  })

  it('rejects node-top fallback and uses handle CSS formula', () => {
    const resolved = resolveMindMapEdgeEndpoint(
      node,
      'target',
      { x: 644.5, y: 209.5 },
      node.data?.style,
      { width: 90, height: 29 }
    )
    expect(resolved.y).toBe(240.5)
  })

  it('uses node side edge X for underline targets (no flush inset gap)', () => {
    const resolved = resolveMindMapEdgeEndpoint(
      node,
      'target',
      { x: 644.5, y: 240 },
      node.data?.style,
      { width: 90, height: 29 }
    )
    expect(resolved.x).toBe(644.5)
  })
})
