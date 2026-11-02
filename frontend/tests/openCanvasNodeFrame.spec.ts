import { describe, expect, it } from 'vitest'

import { frameNodesInOpenCanvas } from '@/composables/diagramCanvas/openCanvasNodeFrame'

const viewport = { x: 0, y: 0, zoom: 1 }

describe('frameNodesInOpenCanvas', () => {
  it('centers the node in the canvas that is left of the order list', () => {
    const framed = frameNodesInOpenCanvas({
      nodes: [
        {
          id: 'n1',
          position: { x: 100, y: 40 },
          dimensions: { width: 80, height: 40 },
        },
      ],
      nodeIds: ['n1'],
      canvasWidth: 1000,
      canvasHeight: 600,
      occludeRightPx: 256,
      minZoom: 0.1,
      maxZoom: 2.2,
      viewport,
    })
    expect(framed).not.toBeNull()
    const zoom = framed?.zoom ?? 0
    const centerX = (100 + 40) * zoom + (framed?.x ?? 0)
    const visibleCenter = (1000 - 256) / 2
    expect(centerX).toBeCloseTo(visibleCenter, 0)
    expect((framed?.y ?? 0) + (40 + 20) * zoom).toBeCloseTo(300, 0)
  })

  it('leaves the viewport alone when nothing covers the right side', () => {
    expect(
      frameNodesInOpenCanvas({
        nodes: [],
        nodeIds: ['n1'],
        canvasWidth: 800,
        canvasHeight: 600,
        occludeRightPx: 0,
        minZoom: 0.1,
        maxZoom: 2,
        viewport,
      })
    ).toBeNull()
  })
})
