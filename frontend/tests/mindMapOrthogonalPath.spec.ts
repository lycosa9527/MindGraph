import { describe, expect, it } from 'vitest'

import {
  MINDMAP_CONNECTOR_FLAT_DY,
  buildMindMapBracketBusPath,
} from '@/utils/mindMapOrthogonalPath'

describe('buildMindMapBracketBusPath rounded tee', () => {
  const trunkX = 560
  const fromX = 500
  const fromY = 335.5
  const toX = 644.5

  it('uses flat horizontal when child Y is within flat threshold of parent', () => {
    const toY = 340
    const path = buildMindMapBracketBusPath(fromX, fromY, toX, toY, trunkX, [280, toY], {
      drawSpine: false,
      siblingToXs: [644.5, toX],
    })
    expect(path).toBe(`M ${trunkX} ${toY} L ${toX} ${toY}`)
    expect(path).not.toContain('Q')
  })

  it('curves downward for branches outside flat threshold', () => {
    const toY = 380
    const path = buildMindMapBracketBusPath(fromX, fromY, toX, toY, trunkX, [280, toY], {
      drawSpine: false,
      siblingToXs: [644.5, toX],
    })
    expect(path).toContain(`Q ${trunkX} ${toY}`)
    expect(path).not.toBe(`M ${trunkX} ${toY} L ${toX} ${toY}`)
  })

  it('sole underline child draws at target Y not source Y', () => {
    const toY = 240
    const path = buildMindMapBracketBusPath(fromX, fromY, toX, toY, trunkX, [toY], {
      singleUnderlineChild: true,
    })
    expect(path).toBe(`M ${fromX} ${fromY} L ${toX} ${toY}`)
  })

  it('respects flat threshold constant for near-parent bottom branch', () => {
    expect(MINDMAP_CONNECTOR_FLAT_DY).toBeGreaterThan(Math.abs(340 - fromY))
  })
})
