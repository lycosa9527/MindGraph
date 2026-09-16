import { describe, expect, it } from 'vitest'

import { loadSpecForDiagramType } from '@/stores/specLoader'
import { loadBraceMapSpec } from '@/stores/specLoader/braceMap'
import { loadBridgeMapSpec } from '@/stores/specLoader/bridgeMap'
import { loadBubbleMapSpec } from '@/stores/specLoader/bubbleMap'
import { loadCircleMapSpec } from '@/stores/specLoader/circleMap'
import { loadDoubleBubbleMapSpec } from '@/stores/specLoader/doubleBubbleMap'
import { loadMultiFlowMapSpec } from '@/stores/specLoader/multiFlowMap'
import { loadTreeMapSpec } from '@/stores/specLoader/treeMap'
import type { Connection, DiagramNode } from '@/types'
import { isLeftoverBraceMapId, resolveBraceMapAliasId } from '@/utils/braceMapIdentity'
import { isLeftoverBridgeMapId, resolveBridgeMapAliasId } from '@/utils/bridgeMapIdentity'
import { isLeftoverBubbleMapId, resolveBubbleMapAliasId } from '@/utils/bubbleMapIdentity'
import { isLeftoverCircleMapId, resolveCircleMapAliasId } from '@/utils/circleMapIdentity'
import {
  isLeftoverDoubleBubbleId,
  resolveDoubleBubbleMapAliasId,
} from '@/utils/doubleBubbleMapIdentity'
import { isLeftoverMultiFlowMapId, resolveMultiFlowMapAliasId } from '@/utils/multiFlowMapIdentity'
import { migrateThinkingMapIdentityIds } from '@/utils/thinkingMapIdentity'
import { isLeftoverTreeMapId, resolveTreeMapAliasId } from '@/utils/treeMapIdentity'

function leftoverCircle(): { nodes: DiagramNode[]; connections: Connection[] } {
  return {
    nodes: [
      { id: 'topic', type: 'topic', text: 'Topic', position: { x: 0, y: 0 } },
      { id: 'outer-boundary', type: 'boundary', text: '', position: { x: 0, y: 0 } },
      { id: 'context-0', type: 'bubble', text: 'A', position: { x: 40, y: 0 } },
      { id: 'context-1', type: 'bubble', text: 'B', position: { x: 80, y: 0 } },
    ],
    connections: [],
  }
}

function leftoverBubble(): { nodes: DiagramNode[]; connections: Connection[] } {
  return {
    nodes: [
      { id: 'topic', type: 'topic', text: 'Topic', position: { x: 0, y: 0 } },
      { id: 'bubble-0', type: 'bubble', text: 'A', position: { x: 40, y: 0 } },
      { id: 'bubble-1', type: 'bubble', text: 'B', position: { x: 80, y: 0 } },
    ],
    connections: [
      { id: 'edge-topic-bubble-0', source: 'topic', target: 'bubble-0' },
      { id: 'edge-topic-bubble-1', source: 'topic', target: 'bubble-1' },
    ],
  }
}

function leftoverDoubleBubble(): { nodes: DiagramNode[]; connections: Connection[] } {
  return {
    nodes: [
      { id: 'left-topic', type: 'topic', text: 'A', position: { x: 0, y: 0 } },
      { id: 'right-topic', type: 'topic', text: 'B', position: { x: 200, y: 0 } },
      { id: 'similarity-0', type: 'bubble', text: 'Same', position: { x: 100, y: 0 } },
      { id: 'left-diff-0', type: 'bubble', text: 'LA', position: { x: 0, y: 80 } },
      { id: 'right-diff-0', type: 'bubble', text: 'RA', position: { x: 200, y: 80 } },
    ],
    connections: [
      { id: 'edge-left-topic-similarity-0', source: 'left-topic', target: 'similarity-0' },
      { id: 'edge-right-topic-similarity-0', source: 'right-topic', target: 'similarity-0' },
    ],
  }
}

function leftoverTree(): { nodes: DiagramNode[]; connections: Connection[] } {
  return {
    nodes: [
      { id: 'tree-topic', type: 'topic', text: 'Root', position: { x: 0, y: 0 } },
      {
        id: 'tree-cat-0',
        type: 'branch',
        text: 'Cat',
        position: { x: 0, y: 40 },
        data: { nodeType: 'branch' },
      },
      {
        id: 'tree-leaf-0-0',
        type: 'branch',
        text: 'Leaf',
        position: { x: 0, y: 80 },
        data: { nodeType: 'leaf' },
      },
    ],
    connections: [
      { id: 'edge-tree-topic-tree-cat-0', source: 'tree-topic', target: 'tree-cat-0' },
      { id: 'edge-tree-cat-0-tree-leaf-0-0', source: 'tree-cat-0', target: 'tree-leaf-0-0' },
    ],
  }
}

function leftoverBrace(): { nodes: DiagramNode[]; connections: Connection[] } {
  return {
    nodes: [
      { id: 'brace-whole', type: 'topic', text: 'Whole', position: { x: 0, y: 0 } },
      { id: 'brace-part-0', type: 'brace', text: 'Part', position: { x: 80, y: 0 } },
      { id: 'brace-subpart-0-0', type: 'brace', text: 'Sub', position: { x: 160, y: 0 } },
    ],
    connections: [
      { id: 'edge-brace-whole-brace-part-0', source: 'brace-whole', target: 'brace-part-0' },
      {
        id: 'edge-brace-part-0-brace-subpart-0-0',
        source: 'brace-part-0',
        target: 'brace-subpart-0-0',
      },
    ],
  }
}

function leftoverMultiFlow(): { nodes: DiagramNode[]; connections: Connection[] } {
  return {
    nodes: [
      { id: 'event', type: 'topic', text: 'Event', position: { x: 100, y: 0 } },
      { id: 'cause-0', type: 'flow', text: 'Cause', position: { x: 0, y: 0 } },
      { id: 'effect-0', type: 'flow', text: 'Effect', position: { x: 200, y: 0 } },
    ],
    connections: [
      { id: 'edge-cause-0-event', source: 'cause-0', target: 'event' },
      { id: 'edge-event-effect-0', source: 'event', target: 'effect-0' },
    ],
  }
}

function leftoverBridge(): { nodes: DiagramNode[]; connections: Connection[] } {
  return {
    nodes: [
      { id: 'dimension-label', type: 'label', text: 'As', position: { x: 0, y: 0 } },
      {
        id: 'pair-0-left',
        type: 'branch',
        text: 'A',
        position: { x: 80, y: 0 },
        data: { pairIndex: 0, position: 'left' },
      },
      {
        id: 'pair-0-right',
        type: 'branch',
        text: 'B',
        position: { x: 80, y: 40 },
        data: { pairIndex: 0, position: 'right' },
      },
    ],
    connections: [],
  }
}

describe('circleMapIdentity', () => {
  it('migrates leftover slot ids to UUIDs and keeps leftover aliases', () => {
    const leftover = leftoverCircle()
    const migrated = migrateThinkingMapIdentityIds(
      'circle_map',
      leftover.nodes,
      leftover.connections
    )
    expect(migrated).not.toBeNull()
    const contexts = migrated!.nodes.filter((n) => n.type === 'bubble')
    expect(contexts).toHaveLength(2)
    for (const node of contexts) {
      expect(isLeftoverCircleMapId(node.id)).toBe(false)
    }
    expect(contexts[0]?.data?.circleMapLegacyId).toBe('context-0')
    expect(resolveCircleMapAliasId('context-0', migrated!.nodes)).toBe(contexts[0]?.id)
    expect(resolveCircleMapAliasId('context-1', migrated!.nodes)).toBe(contexts[1]?.id)
  })

  it('preserves already-stable ids on LLM load then generic reload', () => {
    const first = loadCircleMapSpec({ topic: 'Topic', context: ['A', 'B'] })
    const ids = first.nodes.filter((n) => n.type === 'bubble').map((n) => n.id)
    const second = loadSpecForDiagramType(
      { nodes: first.nodes, connections: first.connections },
      'circle_map'
    )
    expect(second.nodes.filter((n) => n.type === 'bubble').map((n) => n.id)).toEqual(ids)
    expect(ids.every((id) => !isLeftoverCircleMapId(id))).toBe(true)
  })
})

describe('bubbleMapIdentity', () => {
  it('migrates leftover slot ids and rewrites connections', () => {
    const leftover = leftoverBubble()
    const migrated = migrateThinkingMapIdentityIds(
      'bubble_map',
      leftover.nodes,
      leftover.connections
    )
    const bubbles = migrated!.nodes.filter((n) => n.type === 'bubble')
    expect(bubbles.every((n) => !isLeftoverBubbleMapId(n.id))).toBe(true)
    expect(resolveBubbleMapAliasId('bubble-0', migrated!.nodes)).toBe(bubbles[0]?.id)
    expect(migrated!.connections[0]?.target).toBe(bubbles[0]?.id)
  })

  it('keeps UUIDs across LLM load then generic reload', () => {
    const first = loadBubbleMapSpec({ topic: 'Topic', attributes: ['A', 'B'] })
    const ids = first.nodes.filter((n) => n.type === 'bubble').map((n) => n.id)
    const second = loadSpecForDiagramType(
      { nodes: first.nodes, connections: first.connections },
      'bubble_map'
    )
    expect(second.nodes.filter((n) => n.type === 'bubble').map((n) => n.id)).toEqual(ids)
  })
})

describe('doubleBubbleMapIdentity', () => {
  it('migrates leftover slot ids and stamps role + index', () => {
    const leftover = leftoverDoubleBubble()
    const migrated = migrateThinkingMapIdentityIds(
      'double_bubble_map',
      leftover.nodes,
      leftover.connections
    )
    const slots = migrated!.nodes.filter((n) => !['left-topic', 'right-topic'].includes(n.id))
    expect(slots.every((n) => !isLeftoverDoubleBubbleId(n.id))).toBe(true)
    expect(resolveDoubleBubbleMapAliasId('similarity-0', migrated!.nodes)).toBe(
      slots.find((n) => n.data?.doubleBubbleRole === 'similarity')?.id
    )
    expect(migrated!.connections[0]?.target).not.toBe('similarity-0')
  })

  it('honors existing spec ids across reload', () => {
    const first = loadDoubleBubbleMapSpec({
      left: 'A',
      right: 'B',
      similarities: ['Same'],
      leftDifferences: ['LA'],
      rightDifferences: ['RA'],
    })
    const ids = first.nodes.map((n) => n.id)
    const second = loadSpecForDiagramType(
      { nodes: first.nodes, connections: first.connections },
      'double_bubble_map'
    )
    expect(second.nodes.map((n) => n.id)).toEqual(ids)
  })
})

describe('treeMapIdentity', () => {
  it('migrates leftover category/leaf ids and rewrites connections', () => {
    const leftover = leftoverTree()
    const migrated = migrateThinkingMapIdentityIds('tree_map', leftover.nodes, leftover.connections)
    const slots = migrated!.nodes.filter((n) => n.id !== 'tree-topic')
    expect(slots.every((n) => !isLeftoverTreeMapId(n.id))).toBe(true)
    expect(resolveTreeMapAliasId('tree-cat-0', migrated!.nodes)).toBe(
      slots.find((n) => n.data?.nodeType === 'branch')?.id
    )
    expect(migrated!.connections[0]?.target).not.toBe('tree-cat-0')
  })

  it('honors existing spec ids across reload', () => {
    const first = loadTreeMapSpec({
      root: { text: 'Root', children: [{ text: 'Cat', children: [{ text: 'Leaf' }] }] },
    })
    const ids = first.nodes.map((n) => n.id)
    const second = loadSpecForDiagramType(
      { nodes: first.nodes, connections: first.connections },
      'tree_map'
    )
    expect(second.nodes.map((n) => n.id)).toEqual(ids)
  })
})

describe('braceMapIdentity', () => {
  it('migrates leftover part ids and rewrites connections', () => {
    const leftover = leftoverBrace()
    const migrated = migrateThinkingMapIdentityIds(
      'brace_map',
      leftover.nodes,
      leftover.connections
    )
    const parts = migrated!.nodes.filter((n) => n.id !== 'brace-whole')
    expect(parts.every((n) => !isLeftoverBraceMapId(n.id))).toBe(true)
    expect(resolveBraceMapAliasId('brace-part-0', migrated!.nodes)).toBe(parts[0]?.id)
    expect(migrated!.connections[0]?.target).toBe(parts[0]?.id)
  })

  it('mints UUIDs on LLM load', () => {
    const first = loadBraceMapSpec({
      whole: 'Whole',
      parts: [{ name: 'Part', subparts: [{ name: 'Sub' }] }],
    })
    const parts = first.nodes.filter((n) => n.type === 'brace')
    expect(parts.every((n) => !isLeftoverBraceMapId(n.id))).toBe(true)
  })

  it('rewrites leftover flattenTree whole brace-0-0 to reserved brace-whole', () => {
    const migrated = migrateThinkingMapIdentityIds(
      'brace_map',
      [
        { id: 'brace-0-0', type: 'topic', text: 'Whole', position: { x: 0, y: 0 } },
        { id: 'brace-1-0', type: 'brace', text: 'Part', position: { x: 80, y: 0 } },
      ],
      [{ id: 'edge-brace-0-0-brace-1-0', source: 'brace-0-0', target: 'brace-1-0' }]
    )
    expect(migrated!.nodes.some((n) => n.id === 'brace-whole')).toBe(true)
    expect(migrated!.nodes.every((n) => n.id !== 'brace-0-0')).toBe(true)
    expect(resolveBraceMapAliasId('brace-0-0', migrated!.nodes)).toBe('brace-whole')
    expect(migrated!.connections[0]?.source).toBe('brace-whole')
    const part = migrated!.nodes.find((n) => n.type === 'brace')
    expect(part?.id).not.toMatch(/^brace-\d+-\d+$/)
    expect(migrated!.connections[0]?.target).toBe(part?.id)
  })
})

describe('multiFlowMapIdentity', () => {
  it('migrates leftover cause/effect ids and rewrites connections', () => {
    const leftover = leftoverMultiFlow()
    const migrated = migrateThinkingMapIdentityIds(
      'multi_flow_map',
      leftover.nodes,
      leftover.connections
    )
    const slots = migrated!.nodes.filter((n) => n.id !== 'event')
    expect(slots.every((n) => !isLeftoverMultiFlowMapId(n.id))).toBe(true)
    expect(resolveMultiFlowMapAliasId('cause-0', migrated!.nodes)).toBe(slots[0]?.id)
    expect(migrated!.connections[0]?.source).toBe(slots[0]?.id)
  })

  it('keeps UUIDs across generic reload', () => {
    const first = loadMultiFlowMapSpec({ event: 'Event', causes: ['Cause'], effects: ['Effect'] })
    const ids = first.nodes.map((n) => n.id)
    const second = loadSpecForDiagramType(
      { nodes: first.nodes, connections: first.connections },
      'multi_flow_map'
    )
    expect(second.nodes.map((n) => n.id)).toEqual(ids)
  })
})

describe('bridgeMapIdentity', () => {
  it('migrates leftover pair ids and keeps leftover aliases', () => {
    const leftover = leftoverBridge()
    const migrated = migrateThinkingMapIdentityIds(
      'bridge_map',
      leftover.nodes,
      leftover.connections
    )
    const pairs = migrated!.nodes.filter((n) => n.id !== 'dimension-label')
    expect(pairs.every((n) => !isLeftoverBridgeMapId(n.id))).toBe(true)
    expect(resolveBridgeMapAliasId('pair-0-left', migrated!.nodes)).toBe(pairs[0]?.id)
    expect(pairs[0]?.data?.pairIndex).toBe(0)
  })

  it('mints UUIDs on LLM load', () => {
    const first = loadBridgeMapSpec({
      relating_factor: 'As',
      analogies: [{ left: 'A', right: 'B' }],
    })
    const pairs = first.nodes.filter((n) => n.id !== 'dimension-label')
    expect(pairs.every((n) => !isLeftoverBridgeMapId(n.id))).toBe(true)
  })
})
