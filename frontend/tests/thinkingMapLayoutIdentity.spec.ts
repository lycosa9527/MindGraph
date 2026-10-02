/**
 * Layout passes must keep the live dual id and only move coordinates.
 * Brace map used to mint a replacement id on every recalculate.
 */
import { describe, expect, it } from 'vitest'

import { loadSpecForDiagramType } from '@/stores/specLoader'
import { recalculateBraceMapLayout } from '@/stores/specLoader/braceMap'
import { recalculateBridgeMapLayout } from '@/stores/specLoader/bridgeMap'
import { recalculateBubbleMapLayout } from '@/stores/specLoader/bubbleMap'
import { recalculateCircleMapLayout } from '@/stores/specLoader/circleMap'
import { recalculateFlowMapLayout } from '@/stores/specLoader/flowMap'
import { recalculateMultiFlowMapLayout } from '@/stores/specLoader/multiFlowMap'
import { recalculateTreeMapLayout } from '@/stores/specLoader/treeMap'
import type { DiagramNode } from '@/types'

function zeroPositions(nodes: DiagramNode[]): DiagramNode[] {
  return nodes.map((n) => ({ ...n, position: { x: 0, y: 0 } }))
}

function dimensionsOf(nodes: DiagramNode[]): Record<string, { width: number; height: number }> {
  const dims: Record<string, { width: number; height: number }> = {}
  for (const node of nodes) {
    dims[node.id] = { width: 120, height: 40 }
  }
  return dims
}

function expectIdsKeptAndMoved(before: DiagramNode[], after: DiagramNode[]): void {
  const beforeIds = before.map((n) => n.id).sort()
  const afterIds = after.map((n) => n.id).sort()
  expect(afterIds).toEqual(beforeIds)
  const beforeById = new Map(before.map((n) => [n.id, n.position]))
  const moved = after.some((n) => {
    const prev = beforeById.get(n.id)
    return n.position?.x !== prev?.x || n.position?.y !== prev?.y
  })
  expect(moved).toBe(true)
}

describe('thinking map layout keeps live ids', () => {
  it('brace map', () => {
    const loaded = loadSpecForDiagramType(
      {
        whole: 'Phone',
        dimension: 'Parts',
        parts: [{ name: 'Chip', subparts: [{ name: 'Core' }] }],
      },
      'brace_map'
    )
    const zeroed = zeroPositions(loaded.nodes)
    const after = recalculateBraceMapLayout(zeroed, loaded.connections ?? [], dimensionsOf(zeroed))
    expectIdsKeptAndMoved(zeroed, after)
  })

  it('tree map', () => {
    const loaded = loadSpecForDiagramType(
      { root: { text: 'Root', children: [{ text: 'Cat', children: [{ text: 'Leaf' }] }] } },
      'tree_map'
    )
    const zeroed = zeroPositions(loaded.nodes)
    const after = recalculateTreeMapLayout(zeroed, dimensionsOf(zeroed))
    expectIdsKeptAndMoved(zeroed, after)
  })

  it('flow map', () => {
    const loaded = loadSpecForDiagramType(
      {
        title: 'Process',
        steps: ['One'],
        substeps: [{ step: 'One', substeps: ['A'] }],
      },
      'flow_map'
    )
    const zeroed = zeroPositions(loaded.nodes)
    const after = recalculateFlowMapLayout(zeroed, dimensionsOf(zeroed))
    expectIdsKeptAndMoved(zeroed, after)
  })

  it('circle map', () => {
    const loaded = loadSpecForDiagramType({ topic: 'Topic', context: ['A', 'B'] }, 'circle_map')
    const zeroed = zeroPositions(loaded.nodes)
    const after = recalculateCircleMapLayout(zeroed, dimensionsOf(zeroed))
    expectIdsKeptAndMoved(zeroed, after)
  })

  it('bubble map', () => {
    const loaded = loadSpecForDiagramType({ topic: 'Topic', attributes: ['A', 'B'] }, 'bubble_map')
    const zeroed = zeroPositions(loaded.nodes)
    const after = recalculateBubbleMapLayout(zeroed, dimensionsOf(zeroed))
    expectIdsKeptAndMoved(zeroed, after)
  })

  it('bridge map', () => {
    const loaded = loadSpecForDiagramType(
      { relating_factor: 'As', analogies: [{ left: 'A', right: 'B' }] },
      'bridge_map'
    )
    const zeroed = zeroPositions(loaded.nodes)
    const after = recalculateBridgeMapLayout(zeroed, dimensionsOf(zeroed))
    expectIdsKeptAndMoved(zeroed, after)
  })

  it('multi-flow map', () => {
    const loaded = loadSpecForDiagramType(
      { event: 'Event', causes: ['Cause'], effects: ['Effect'] },
      'multi_flow_map'
    )
    const zeroed = zeroPositions(loaded.nodes)
    const after = recalculateMultiFlowMapLayout(zeroed, 160, {}, dimensionsOf(zeroed))
    expectIdsKeptAndMoved(zeroed, after)
  })
})
