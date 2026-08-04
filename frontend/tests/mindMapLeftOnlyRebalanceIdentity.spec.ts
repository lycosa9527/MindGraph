import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  remapMindMapCollapsedPathsAfterReload,
  remapMindMapMeasuredDimensionsAfterReload,
  remapMindMapNodeIdAfterReload,
  remapMindMapNodeIdsAfterReload,
} from '@/stores/diagram/mindMapCollapse'
import {
  mergeMindMapReloadStyles,
  mindMapNodePathKey,
} from '@/stores/diagram/mindMapStylePreservation'
import {
  loadMindMapSpec,
  nodesAndConnectionsToMindMapSpec,
  rebalanceMindMapBranchesIfLeftOnly,
} from '@/stores/specLoader/mindMap'
import { useUIStore } from '@/stores/ui'
import { readMindMapNodeUid } from '@/utils/mindMapNodeUid'
import type { Connection, DiagramNode, NodeStyle } from '@/types'

function uidOf(nodes: DiagramNode[], text: string): string {
  const node = nodes.find((n) => n.text === text && n.id.startsWith('branch-'))
  const uid = readMindMapNodeUid(node)
  if (!uid) throw new Error(`missing uid for ${text}`)
  return uid
}

function idByUid(nodes: DiagramNode[], uid: string): string {
  const node = nodes.find((n) => readMindMapNodeUid(n) === uid)
  if (!node) throw new Error(`missing node for uid ${uid}`)
  return node.id
}

describe('left-only rebalance identity (uid / style / collapse / dims)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      length: 0,
      key: vi.fn(() => null),
    })
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    useUIStore().mindMapCanvasMode = 'v2'
  })

  function buildLeftHeavyMap(): {
    oldNodes: DiagramNode[]
    oldConnections: Connection[]
    newNodes: DiagramNode[]
    newConnections: Connection[]
    movedUid: string
    stayedUid: string
    movedOldId: string
    stayedOldId: string
  } {
    // 1 right + 3 left → delete the right L1 → left-only rebalance moves one left→right.
    const initial = loadMindMapSpec({
      topic: 'Topic',
      rightBranches: [{ text: 'RightGone', children: [{ text: 'RG1' }] }],
      leftBranches: [
        {
          text: 'StayLeft',
          uid: 'uid-stay',
          children: [{ text: 'StayChild', uid: 'uid-stay-child' }],
        },
        {
          text: 'MoveRight',
          uid: 'uid-move',
          children: [{ text: 'MoveChild', uid: 'uid-move-child' }],
        },
        { text: 'AlsoLeft', uid: 'uid-also' },
      ],
      preserveLeftRight: true,
    })

    const extracted = nodesAndConnectionsToMindMapSpec(initial.nodes, initial.connections)
    expect(extracted.rightBranches.map((b) => b.text)).toEqual(['RightGone'])
    expect(extracted.leftBranches.map((b) => b.text)).toEqual([
      'StayLeft',
      'MoveRight',
      'AlsoLeft',
    ])

    const balanced = rebalanceMindMapBranchesIfLeftOnly(extracted.leftBranches, [])
    expect(balanced.redistributed).toBe(true)

    const reloaded = loadMindMapSpec({
      topic: extracted.topic,
      leftBranches: balanced.leftBranches,
      rightBranches: balanced.rightBranches,
      preserveLeftRight: true,
    })

    const movedOldId = initial.nodes.find((n) => n.text === 'MoveRight')?.id
    const stayedOldId = initial.nodes.find((n) => n.text === 'StayLeft')?.id
    if (!movedOldId || !stayedOldId) throw new Error('expected old branch ids')

    return {
      oldNodes: initial.nodes,
      oldConnections: initial.connections,
      newNodes: reloaded.nodes,
      newConnections: reloaded.connections,
      movedUid: 'uid-move',
      stayedUid: 'uid-stay',
      movedOldId,
      stayedOldId,
    }
  }

  it('preserves mindMapUid across side flip after left-only rebalance', () => {
    const { oldNodes, newNodes, movedUid, stayedUid } = buildLeftHeavyMap()

    expect(uidOf(oldNodes, 'MoveRight')).toBe(movedUid)
    expect(uidOf(newNodes, 'MoveRight')).toBe(movedUid)
    expect(uidOf(newNodes, 'StayLeft')).toBe(stayedUid)

    const movedNewId = idByUid(newNodes, movedUid)
    const stayedNewId = idByUid(newNodes, stayedUid)
    expect(movedNewId.startsWith('branch-r-')).toBe(true)
    expect(stayedNewId.startsWith('branch-l-')).toBe(true)
    expect(uidOf(newNodes, 'MoveChild')).toBe('uid-move-child')
  })

  it('remaps selection and measured sizes when a branch flips side', () => {
    const {
      oldNodes,
      oldConnections,
      newNodes,
      newConnections,
      movedOldId,
      stayedOldId,
      movedUid,
      stayedUid,
    } = buildLeftHeavyMap()

    expect(
      remapMindMapNodeIdAfterReload(
        movedOldId,
        oldNodes,
        oldConnections,
        newNodes,
        newConnections
      )
    ).toBe(idByUid(newNodes, movedUid))

    expect(
      remapMindMapNodeIdsAfterReload(
        [movedOldId, stayedOldId, 'branch-r-1-0'],
        oldNodes,
        oldConnections,
        newNodes,
        newConnections
      )
    ).toEqual([idByUid(newNodes, movedUid), idByUid(newNodes, stayedUid)])

    const dims = remapMindMapMeasuredDimensionsAfterReload(
      { [movedOldId]: 140, [stayedOldId]: 120 },
      { [movedOldId]: 36, [stayedOldId]: 34 },
      oldNodes,
      oldConnections,
      newNodes,
      newConnections
    )
    expect(dims.widths[idByUid(newNodes, movedUid)]).toBe(140)
    expect(dims.heights[idByUid(newNodes, movedUid)]).toBe(36)
    expect(dims.widths[idByUid(newNodes, stayedUid)]).toBe(120)
  })

  it('keeps per-node styles on the flipped branch via uid remap', () => {
    const { oldNodes, oldConnections, newNodes, newConnections, movedOldId, movedUid } =
      buildLeftHeavyMap()

    const existingStyles: Record<string, NodeStyle> = {
      [movedOldId]: { fontSize: 22, textColor: '#112233' },
    }
    const merged = mergeMindMapReloadStyles(
      oldNodes,
      oldConnections,
      newNodes,
      newConnections,
      existingStyles,
      null,
      null,
      remapMindMapNodeIdAfterReload
    )

    const movedNewId = idByUid(newNodes, movedUid)
    expect(merged[movedNewId]?.fontSize).toBe(22)
    expect(merged[movedNewId]?.textColor).toBe('#112233')
    expect(merged[movedOldId]).toBeUndefined()
  })

  it('keeps collapse state when the collapsed branch moves to the other side', () => {
    const { oldNodes, oldConnections, newNodes, newConnections, movedOldId, movedUid } =
      buildLeftHeavyMap()

    const oldPath = mindMapNodePathKey(movedOldId, oldConnections)
    expect(oldPath).toBeTruthy()

    const remapped = remapMindMapCollapsedPathsAfterReload(
      oldNodes,
      oldConnections,
      newNodes,
      newConnections,
      [oldPath as string]
    )

    const movedNewId = idByUid(newNodes, movedUid)
    const newPath = mindMapNodePathKey(movedNewId, newConnections)
    expect(remapped).toEqual([newPath])
    expect(newPath?.startsWith('r/')).toBe(true)
  })
})
