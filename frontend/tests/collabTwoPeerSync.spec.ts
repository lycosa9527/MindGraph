import { describe, expect, it } from 'vitest'

import {
  remapCollabConnectionEndpoints,
  spliceCollabConnection,
} from '@/utils/collabConnectionInsert'
import { resolveMindMapAliasId } from '@/utils/mindMapIdentityMigrate'
import type { Connection, DiagramNode } from '@/types'

const TOPIC = 'topic'
const CHILD_A = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
const CHILD_B = 'bbbbbbbb-cccc-dddd-eeee-ffffffffffff'
const CHILD_C = 'cccccccc-dddd-eeee-ffff-000000000000'
const CHILD_D = 'dddddddd-eeee-ffff-0000-111111111111'

type Canvas = {
  nodes: DiagramNode[]
  connections: Connection[]
}

function branch(id: string, text: string, legacy?: string): DiagramNode {
  return {
    id,
    text,
    type: 'branch',
    data: legacy ? { mindMapUid: id, mindMapLegacyId: legacy } : { mindMapUid: id },
  }
}

function baseline(): Canvas {
  return {
    nodes: [
      { id: TOPIC, text: '主题', type: 'topic' },
      branch(CHILD_A, 'A', 'branch-r-1-0'),
      branch(CHILD_B, 'B', 'branch-r-1-1'),
    ],
    connections: [
      { id: 'e-a', source: TOPIC, target: CHILD_A },
      { id: 'e-b', source: TOPIC, target: CHILD_B },
    ],
  }
}

function childOrder(canvas: Canvas): string[] {
  return canvas.connections.filter((conn) => conn.source === TOPIC).map((conn) => conn.target)
}

function applyPeerPatch(
  canvas: Canvas,
  nodes: Array<Record<string, unknown>>,
  connections: Array<Record<string, unknown>>
): void {
  const remap = (hint: string): string => resolveMindMapAliasId(hint, canvas.nodes) ?? hint
  for (const row of nodes) {
    const rawId = typeof row.id === 'string' ? row.id : ''
    if (!rawId) continue
    const nodeId = remap(rawId)
    const next = { ...row, id: nodeId } as DiagramNode
    const existing = canvas.nodes.findIndex((node) => node.id === nodeId)
    if (existing >= 0) {
      canvas.nodes[existing] = { ...canvas.nodes[existing], ...next }
    } else {
      canvas.nodes.push(next)
    }
  }
  for (const row of connections) {
    spliceCollabConnection(canvas.connections, remapCollabConnectionEndpoints(row, remap))
  }
}

describe('two-peer mind-map add sync', () => {
  it('Alice add then Bob add is visible on both canvases', () => {
    const alice = baseline()
    const bob = baseline()

    const aliceAdd = [
      branch(CHILD_C, 'C') as unknown as Record<string, unknown>,
    ]
    const aliceEdge = [
      { id: 'e-c', source: TOPIC, target: CHILD_C, insert_after_target: CHILD_A },
    ]
    applyPeerPatch(alice, aliceAdd, aliceEdge)
    applyPeerPatch(bob, aliceAdd, aliceEdge)
    expect(bob.nodes.some((node) => node.id === CHILD_C)).toBe(true)
    expect(childOrder(alice)).toEqual(childOrder(bob))
    expect(childOrder(bob)).toEqual([CHILD_A, CHILD_C, CHILD_B])

    const bobAdd = [branch(CHILD_D, 'D') as unknown as Record<string, unknown>]
    const bobEdge = [
      { id: 'e-d', source: TOPIC, target: CHILD_D, insert_after_target: CHILD_B },
    ]
    applyPeerPatch(bob, bobAdd, bobEdge)
    applyPeerPatch(alice, bobAdd, bobEdge)
    expect(alice.nodes.some((node) => node.id === CHILD_D)).toBe(true)
    expect(childOrder(alice)).toEqual([CHILD_A, CHILD_C, CHILD_B, CHILD_D])
    expect(childOrder(alice)).toEqual(childOrder(bob))
  })

  it('leftover sibling hint from Alice lands beside the UUID child on Bob', () => {
    const alice = baseline()
    const bob = baseline()
    const nodes = [branch(CHILD_C, 'C') as unknown as Record<string, unknown>]
    const conns = [
      { id: 'e-c', source: TOPIC, target: CHILD_C, insert_after_target: 'branch-r-1-0' },
    ]
    applyPeerPatch(alice, nodes, conns)
    applyPeerPatch(bob, nodes, conns)
    expect(childOrder(alice)).toEqual([CHILD_A, CHILD_C, CHILD_B])
    expect(childOrder(bob)).toEqual(childOrder(alice))
  })
})
