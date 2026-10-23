import { describe, expect, it } from 'vitest'

import { nodesAndConnectionsToMindMapSpec } from '@/stores/specLoader/mindMap'
import type { Connection, DiagramNode } from '@/types'
import {
  collapseDuplicateMindMapNodes,
  migrateMindMapIdentityIds,
  mindMapIdentityAliases,
  mindMapPatchCarriesBranchIdentity,
  resolveMindMapAliasId,
  resolveMindMapIdentityId,
  resolveMindMapPatchTargetId,
} from '@/utils/mindMapIdentityMigrate'
import {
  isMindMapL1,
  mindMapLocationPathKey,
  mindMapNodeDepth,
  mindMapNodeSide,
} from '@/utils/mindMapLocation'
import { stableMindMapIdentityId } from '@/utils/mindMapStableId'

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
    expect(
      mindMapNodeSide('uid-diy', { nodes: migrated.nodes, connections: migrated.connections })
    ).toBe(before.side)
    expect(
      mindMapNodeDepth('uid-diy', { nodes: migrated.nodes, connections: migrated.connections })
    ).toBe(before.depth)
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
    const dupes: DiagramNode[] = [...nodes, { id: 'uid-diy-2', type: 'branch', text: 'DIY' }]
    expect(resolveMindMapIdentityId('DIY', dupes)).toBeNull()
  })

  it('collab alias resolve does not match unique labels', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', type: 'topic', text: 'Cars' },
      { id: 'uid-diy', type: 'branch', text: 'DIY' },
    ]
    expect(resolveMindMapIdentityId('DIY', nodes)).toBe('uid-diy')
    expect(resolveMindMapAliasId('DIY', nodes)).toBeNull()
    expect(resolveMindMapAliasId('uid-diy', nodes)).toBe('uid-diy')
  })

  it('mints the same id for a leftover branch on every client', () => {
    const once = migrateMindMapIdentityIds(
      [
        { id: 'topic', type: 'topic', text: '平面直角坐标系' },
        { id: 'branch-r-1-0', type: 'branch', text: '横轴' },
      ],
      [{ id: 'e', source: 'topic', target: 'branch-r-1-0' }]
    )
    const twice = migrateMindMapIdentityIds(
      [
        { id: 'topic', type: 'topic', text: '平面直角坐标系' },
        { id: 'branch-r-1-0', type: 'branch', text: '横轴' },
      ],
      [{ id: 'e', source: 'topic', target: 'branch-r-1-0' }]
    )
    const branch = once.nodes.find((node) => node.text === '横轴')
    expect(branch?.id).toBe('8db35dc2-790c-5b54-94f9-7f8be0e8683c')
    expect(branch?.id).toBe(stableMindMapIdentityId('branch-r-1-0'))
    expect(twice.nodes.find((node) => node.text === '横轴')?.id).toBe(branch?.id)
    expect(branch?.id).not.toBe('branch-r-1-0')
  })

  it('treats a position echo as having no branch identity', () => {
    expect(
      mindMapPatchCarriesBranchIdentity({ id: 'uuid-stranger', position: { x: 1, y: 2 } })
    ).toBe(false)
    expect(
      mindMapPatchCarriesBranchIdentity({
        id: 'uuid-new',
        type: 'branch',
        text: '纵轴',
      })
    ).toBe(true)
  })

  it('resolves a remembered peer id with no patch data', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', type: 'topic', text: '平面直角坐标系' },
      {
        id: 'uuid-server',
        type: 'branch',
        text: '横轴',
        data: {
          mindMapUid: 'uuid-server',
          mindMapLegacyId: 'branch-r-1-0',
          mindMapAliasIds: ['uuid-client'],
        },
      },
    ]
    expect(mindMapIdentityAliases(nodes)['uuid-client']).toBe('uuid-server')
    expect(resolveMindMapPatchTargetId('uuid-client', undefined, nodes)).toBe('uuid-server')
  })

  it('collapses a second collab identity of the same branch', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', type: 'topic', text: '平面直角坐标系', position: { x: 0, y: 0 } },
      {
        id: 'uuid-server',
        type: 'branch',
        text: '横轴',
        position: { x: 220, y: 0 },
        data: { mindMapUid: 'uuid-server', mindMapLegacyId: 'branch-r-1-0', mindMapSide: 'right' },
      },
      {
        id: 'uuid-client',
        type: 'branch',
        text: '横轴',
        position: { x: -40, y: 30 },
        data: { mindMapUid: 'uuid-client', mindMapLegacyId: 'branch-r-1-0', mindMapSide: 'right' },
      },
    ]
    const connections: Connection[] = [
      { id: 'e-server', source: 'topic', target: 'uuid-server' },
      { id: 'e-client', source: 'topic', target: 'uuid-client' },
    ]
    const collapsed = collapseDuplicateMindMapNodes(nodes, connections)
    expect(collapsed.nodes.map((node) => node.id)).toEqual(['topic', 'uuid-server'])
    expect(collapsed.connections.map((conn) => conn.target)).toEqual(['uuid-server'])
    const live = nodes.filter((node) => node.id !== 'uuid-client')
    expect(resolveMindMapPatchTargetId('uuid-client', nodes[2]?.data, live)).toBe('uuid-server')
  })

  it('extract keeps uid and leftover positional id for a later layout reload', () => {
    const { nodes, connections } = positionalTree()
    const migrated = migrateMindMapIdentityIds(nodes, connections)
    const extracted = nodesAndConnectionsToMindMapSpec(migrated.nodes, migrated.connections)
    expect(extracted.rightBranches[0]?.uid).toBe('uid-diy')
    expect(extracted.rightBranches[0]?.legacyId).toBe('branch-r-1-0')
  })
})
