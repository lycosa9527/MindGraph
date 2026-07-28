import { describe, expect, it } from 'vitest'

import {
  MINDMAP_CONNECTOR_FLAT_DY,
  MINDMAP_TOPIC_TRUNK_MIN_OFFSET,
  buildMindMapBracketBusPath,
  computeMindMapSharedTrunkX,
} from '@/utils/mindMapOrthogonalPath'

describe('buildMindMapBracketBusPath rounded tee', () => {
  const trunkX = 560
  const fromX = 500
  const fromY = 335.5
  const toX = 644.5

  it('rounds near-parent child on a multi-sibling bus (not sharp 90° at spine)', () => {
    // Matches production debug: parent Y≈250, first child dy<FLAT_DY, sibling farther down.
    const parentY = 250
    const nearChildY = 246
    const farChildY = 286
    expect(MINDMAP_CONNECTOR_FLAT_DY).toBeGreaterThan(Math.abs(nearChildY - parentY))

    const spinePath = buildMindMapBracketBusPath(
      fromX,
      parentY,
      toX,
      nearChildY,
      trunkX,
      [nearChildY, farChildY],
      {
        drawSpine: true,
        siblingToXs: [toX, toX],
      }
    )
    expect(spinePath).toContain(`Q ${trunkX} ${nearChildY}`)

    // Non-spine edges are horizontal stubs only (fillet lives on the spine path).
    const stubPath = buildMindMapBracketBusPath(
      fromX,
      parentY,
      toX,
      nearChildY,
      trunkX,
      [nearChildY, farChildY],
      {
        drawSpine: false,
        siblingToXs: [toX, toX],
      }
    )
    expect(stubPath).not.toContain('Q')
    expect(stubPath).toMatch(/^M [\d.]+ 246 L /)
  })

  it('keeps flat tee when every sibling is within flat threshold of parent', () => {
    const toY = 340
    const path = buildMindMapBracketBusPath(fromX, fromY, toX, toY, trunkX, [338, toY], {
      drawSpine: false,
      siblingToXs: [toX, toX],
    })
    expect(path).toBe(`M ${trunkX} ${toY} L ${toX} ${toY}`)
    expect(path).not.toContain('Q')
  })

  it('curves downward for branches outside flat threshold', () => {
    const toY = 380
    const spinePath = buildMindMapBracketBusPath(fromX, fromY, toX, toY, trunkX, [280, toY], {
      drawSpine: true,
      siblingToXs: [644.5, toX],
    })
    expect(spinePath).toContain(`Q ${trunkX} ${toY}`)
    // Fillet is continuous from the bus (L → Q), not a second subpath along the trunk.
    expect(spinePath).toContain(`L ${trunkX} `)
    expect(spinePath).not.toMatch(new RegExp(`M ${trunkX} [\\d.]+ Q ${trunkX} ${toY}`))
  })

  it('does not retrace the bus under a translucent tee (no M→Q along trunk)', () => {
    const toY = 380
    const farY = 280
    const path = buildMindMapBracketBusPath(fromX, fromY, toX, toY, trunkX, [farY, toY], {
      drawSpine: true,
      siblingToXs: [toX, toX],
    })
    // Old bug: spine subpath + `M trunkX approachY Q …` double-painted the join.
    expect(path).not.toMatch(new RegExp(`M ${trunkX} [\\d.]+ Q ${trunkX} `))
    expect(path).toContain(`Q ${trunkX} ${toY}`)
    expect(path).toContain(`Q ${trunkX} ${farY}`)
  })

  it('sole underline child draws at target Y not source Y', () => {
    const toY = 240
    const path = buildMindMapBracketBusPath(fromX, fromY, toX, toY, trunkX, [toY], {
      singleUnderlineChild: true,
    })
    expect(path).toBe(`M ${fromX} ${fromY} L ${toX} ${toY}`)
  })
})

describe('computeMindMapSharedTrunkX tee clearance', () => {
  it('keeps trunk before the child when gap is shorter than the min offset', () => {
    const sourceX = 500
    // Effective gap 22px < MINDMAP_TOPIC_TRUNK_MIN_OFFSET (28) — old code overshot.
    const toX = sourceX + 22
    const trunkX = computeMindMapSharedTrunkX(sourceX, [toX], toX)

    expect(MINDMAP_TOPIC_TRUNK_MIN_OFFSET).toBeGreaterThan(22)
    expect(trunkX).toBeGreaterThan(sourceX)
    expect(trunkX).toBeLessThan(toX)

    const fromY = 300
    const toY = 340
    const path = buildMindMapBracketBusPath(sourceX, fromY, toX, toY, trunkX, [260, toY], {
      drawSpine: true,
      siblingToXs: [toX, toX],
    })
    expect(path).toContain('Q ')
  })
})

describe('edge endpoint width fallback order', () => {
  it('prefers estimatedWidth over vue-flow dimensions (matches layout)', async () => {
    const { resolveMindMapEdgeEndpoint } = await import('@/utils/mindMapEdgeEndpoints')
    const point = resolveMindMapEdgeEndpoint(
      {
        id: 'branch-r-1-0',
        position: { x: 520, y: 200 },
        dimensions: { width: 140, height: 40 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
      'source',
      { x: 0, y: 0 },
      { nodeShape: 'underline' },
      undefined,
      undefined
    )
    // Right-side source = left + estimated width (90), not vue-flow 140.
    expect(point.x).toBeCloseTo(520 + 90, 5)
  })
})
