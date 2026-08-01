import { describe, expect, it } from 'vitest'

import { computePanToKeepNodeInSafeFraction } from '@/utils/mindMapEnsureNodeVisible'

describe('computePanToKeepNodeInSafeFraction', () => {
  const base = {
    viewport: { x: 0, y: 0, zoom: 1 },
    viewWidth: 1000,
    viewHeight: 800,
    safeFraction: 0.75,
    chromeInsets: { top: 0, right: 0, bottom: 0, left: 0 },
  }

  it('no-ops when the node is already inside the central 75%', () => {
    const result = computePanToKeepNodeInSafeFraction({
      ...base,
      node: { x: 400, y: 300, width: 100, height: 40 },
    })
    expect(result.changed).toBe(false)
    expect(result.viewport).toEqual(base.viewport)
  })

  it('pans left when the node is past the right safe edge (keeps zoom)', () => {
    const result = computePanToKeepNodeInSafeFraction({
      ...base,
      node: { x: 920, y: 300, width: 100, height: 40 },
    })
    expect(result.changed).toBe(true)
    expect(result.viewport.zoom).toBe(1)
    expect(result.viewport.x).toBeLessThan(0)
    expect(result.viewport.y).toBe(0)
  })

  it('pans down when the node is above the top safe edge', () => {
    const result = computePanToKeepNodeInSafeFraction({
      ...base,
      node: { x: 400, y: -20, width: 100, height: 40 },
    })
    expect(result.changed).toBe(true)
    expect(result.viewport.zoom).toBe(1)
    expect(result.viewport.y).toBeGreaterThan(0)
    expect(result.viewport.x).toBe(0)
  })

  it('respects chrome insets when computing the usable safe zone', () => {
    const result = computePanToKeepNodeInSafeFraction({
      ...base,
      chromeInsets: { top: 48, right: 40, bottom: 88, left: 40 },
      node: { x: 40, y: 48, width: 80, height: 40 },
    })
    // Near chrome corner — should still pan into the inner 75% of usable area.
    expect(result.changed).toBe(true)
    expect(result.viewport.zoom).toBe(1)
  })
})
