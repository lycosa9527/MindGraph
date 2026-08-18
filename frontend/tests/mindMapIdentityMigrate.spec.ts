import { describe, expect, it } from 'vitest'

import { nodesAndConnectionsToMindMapSpec } from '@/stores/specLoader/mindMap'
import {
  migrateMindMapIdentityIds,
  mindMapIdentityAliases,
  resolveMindMapIdentityId,
} from '@/utils/mindMapIdentityMigrate'
import {
  isMindMapL1,
  mindMapLocationPathKey,
  mindMapNodeDepth,
  mindMapNodeSide,
} from '@/utils/mindMapLocation'
import type { Connection, DiagramNode } from '@/types'

function positionalTree(): { nodes: DiagramNode[]; connections: Connection[] } {
  return {
    nodes: [
      { id: 'topic', type: 'topic', text: 'Cars' },
      {
        id: 'branch-r-1-0',
        type: 'branch',
        text: 'DIY',
        data: { mindMapUid: 'uid-diy', mindMapSide: 'right', mindMapDepth: 1 },
      },
      {
        id: 'branch-r-2-0',
        type: 'branch',
        text: 'Paint',
        data: { mindMapUid: 'uid-paint', mindMapSide: 'right', mindMapDepth: 2 },
      },
    ],
    connections: [
      { id: 'e1', source: 'topic', target: 'branch-r-1-0', sourceHandle: 'mindmap-right-0' },
      { id: 'e2', source: 'branch-r-1-0', target: 'branch-r-2-0' },
    ],
  }
}

describe('mind-map identity invert', () => {
  it('keeps side/depth/L1 the same after migrate', () => {
    const { nodes, connections } = positionalTree()
    const before = {
      side: mindMapNodeSide('branch-r-1-0', { nodes, connections }),
      depth: mindMapNodeDepth('branch-r-1-0', { nodes, connections }),
      l1: isMindMapL1('branch-r-1-0', connections),
      path: mindMapLocationPathKey('branch-r-1-0', connections, { nodes }),
    }
    const migrated = migrateMindMapIdentityIds(nodes, connections)
    expect(migrated.idMap['branch-r-1-0']).toBe('uid-diy')
    expect(mindMapNodeSide('uid-diy', { nodes: migrated.nodes, connections: migrated.connections })).toBe(
      before.side
    )
    expect(mindMapNodeDepth('uid-diy', { nodes: migrated.nodes, connections: migrated.connections })).toBe(
      before.depth
    )
    expect(isMindMapL1('uid-diy', migrated.connections)).toBe(before.l1)
    expect(mindMapLocationPathKey('uid-diy', migrated.connections, { nodes: migrated.nodes })).toBe(
      before.path
    )
    expect(before).toEqual({ side: 'right', depth: 1, l1: true, path: 'r/0' })
  })

  it('rewrites edges and style keys when migrating a positional spec', () => {
    const { nodes, connections } = positionalTree()
    const migrated = migrateMindMapIdentityIds(nodes, connections, {
      'branch-r-1-0': { backgroundColor: '#eee' },
    })
    const diy = migrated.nodes.find((node) => node.text === 'DIY')
    expect(diy?.id).toBe('uid-diy')
    expect(migrated.connections[0].target).toBe('uid-diy')
    expect(migrated.nodeStyles?.['uid-diy']?.backgroundColor).toBe('#eee')
    expect(diy?.text).toBe('DIY')
  })

  it('does not recycle the survivor id when A is deleted', () => {
    const { nodes, connections } = positionalTree()
    const migrated = migrateMindMapIdentityIds(nodes, connections)
    const diyId = migrated.nodes.find((node) => node.text === 'DIY')?.id
    const paintId = migrated.nodes.find((node) => node.text === 'Paint')?.id
    const survivors = migrated.nodes.filter((node) => node.id !== diyId)
    expect(paintId).toBe('uid-paint')
    expect(survivors.some((node) => node.id === paintId)).toBe(true)
  })

  it('resolves leftover positional focus ids through aliases', () => {
    const { nodes, connections } = positionalTree()
    const migrated = migrateMindMapIdentityIds(nodes, connections)
    const aliases = mindMapIdentityAliases(migrated.nodes)
    expect(aliases['branch-r-1-0']).toBe('uid-diy')
    expect(resolveMindMapIdentityId('branch-r-1-0', migrated.nodes)).toBe('uid-diy')
    expect(resolveMindMapIdentityId('uid-diy', migrated.nodes)).toBe('uid-diy')
  })

  it('migrates leftover branch_0 invented ids to UUIDs', () => {
    const migrated = migrateMindMapIdentityIds(
      [
        { id: 'topic', type: 'topic', text: 'Cars' },
        { id: 'branch_0', type: 'branch', text: 'DIY' },
      ],
      [{ id: 'e0', source: 'topic', target: 'branch_0' }]
    )
    const diy = migrated.nodes.find((node) => node.text === 'DIY')
    expect(diy?.id).not.toBe('branch_0')
    expect(diy?.data?.mindMapLegacyId).toBe('branch_0')
    expect(migrated.connections[0]?.target).toBe(diy?.id)
    expect(resolveMindMapIdentityId('branch_0', migrated.nodes)).toBe(diy?.id)
  })

  it('resolves a unique label when leftover id was not stamped', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', type: 'topic', text: 'Cars' },
      { id: 'uid-diy', type: 'branch', text: 'DIY' },
      { id: 'uid-paint', type: 'branch', text: 'Paint' },
    ]
    expect(resolveMindMapIdentityId('DIY', nodes)).toBe('uid-diy')
    const dupes: DiagramNode[] = [
      ...nodes,
      { id: 'uid-diy-2', type: 'branch', text: 'DIY' },
    ]
    expect(resolveMindMapIdentityId('DIY', dupes)).toBeNull()
  })

  it('extract keeps uid and leftover positional id for a later layout reload', () => {
    const { nodes, connections } = positionalTree()
    const migrated = migrateMindMapIdentityIds(nodes, connections)
    const extracted = nodesAndConnectionsToMindMapSpec(migrated.nodes, migrated.connections)
    expect(extracted.rightBranches[0]?.uid).toBe('uid-diy')
    expect(extracted.rightBranches[0]?.legacyId).toBe('branch-r-1-0')
  })
})
