import { describe, expect, it } from 'vitest'

import { insertMindMapSiblingInPlace } from '@/stores/diagram/mindMapSiblingInsert'
import type { Connection, DiagramNode } from '@/types'
import { isMindMapL1, mindMapNodeSide } from '@/utils/mindMapLocation'
import { MINDMAP_NODE_UID_DATA_KEY } from '@/utils/mindMapNodeUid'

const IDENTITY_ID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function topicTargets(
  connections: Connection[],
  nodes: DiagramNode[],
  side?: 'left' | 'right'
): string[] {
  return connections
    .filter((connection) => connection.source === 'topic')
    .map((connection) => connection.target)
    .filter((id) => !side || mindMapNodeSide(id, { nodes, connections }) === side)
}

function sampleGraph(): { nodes: DiagramNode[]; connections: Connection[] } {
  const nodes: DiagramNode[] = [
    {
      id: 'topic',
      text: '主题',
      type: 'topic',
      position: { x: 400, y: 300 },
      data: { estimatedWidth: 80, estimatedHeight: 40 },
    },
    {
      id: 'branch-r-1-0',
      text: '分支A',
      type: 'branch',
      position: { x: 520, y: 200 },
      data: {
        estimatedWidth: 90,
        estimatedHeight: 36,
        [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a',
      },
    },
    {
      id: 'branch-r-1-1',
      text: '分支B',
      type: 'branch',
      position: { x: 520, y: 280 },
      data: {
        estimatedWidth: 90,
        estimatedHeight: 36,
        [MINDMAP_NODE_UID_DATA_KEY]: 'uid-b',
      },
    },
  ]
  const connections: Connection[] = [
    {
      id: 'edge-topic-branch-r-1-0',
      source: 'topic',
      target: 'branch-r-1-0',
      sourceHandle: 'mindmap-right',
      targetHandle: 'left',
    },
    {
      id: 'edge-topic-branch-r-1-1',
      source: 'topic',
      target: 'branch-r-1-1',
      sourceHandle: 'mindmap-right',
      targetHandle: 'left',
    },
  ]
  return { nodes, connections }
}

describe('insertMindMapSiblingInPlace', () => {
  it('mints one id, keeps existing ids, and splices connection order', () => {
    const { nodes, connections } = sampleGraph()
    const result = insertMindMapSiblingInPlace(nodes, connections, {
      anchorNodeId: 'branch-r-1-0',
      text: '新分支',
      position: 'below',
    })
    expect(result).toBeTruthy()
    if (!result) {
      throw new Error('expected insert result')
    }
    expect(result.newNodeId).toMatch(IDENTITY_ID_RE)
    expect(result.newNodeId).not.toBe('branch-r-1-0')
    expect(result.newNodeId).not.toBe('branch-r-1-1')

    const ids = result.nodes.map((n) => n.id)
    expect(ids).toContain('branch-r-1-0')
    expect(ids).toContain('branch-r-1-1')
    expect(ids).toContain(result.newNodeId)

    const rightTargets = result.connections.filter((c) => c.source === 'topic').map((c) => c.target)
    expect(rightTargets).toEqual(['branch-r-1-0', result.newNodeId, 'branch-r-1-1'])
    expect(result.seededStyle.nodeShape).toBeTruthy()
    expect(result.nodes.find((n) => n.id === result.newNodeId)?.style).toEqual(result.seededStyle)
  })

  it('mints style matching same-side sibling (not opposite side)', () => {
    const nodes: DiagramNode[] = [
      {
        id: 'topic',
        text: '中心主题',
        type: 'topic',
        position: { x: 400, y: 300 },
        data: { estimatedWidth: 100, estimatedHeight: 40 },
      },
      {
        id: 'branch-r-1-0',
        text: '右',
        type: 'branch',
        position: { x: 560, y: 220 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
        style: {
          backgroundColor: '#dbeafe',
          borderColor: '#0f766e',
          nodeShape: 'oval',
        },
      },
      {
        id: 'branch-l-1-0',
        text: '左',
        type: 'branch',
        position: { x: 200, y: 220 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
        style: {
          backgroundColor: '#ff0000',
          borderColor: '#990000',
          nodeShape: 'rounded',
        },
      },
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-l-1-0' },
    ]
    const result = insertMindMapSiblingInPlace(nodes, connections, {
      anchorNodeId: 'branch-r-1-0',
      text: '新分支',
      position: 'below',
      themeId: 'vibrantBlue',
      diagramStyleId: 'bubble',
      nodeStyles: {
        'branch-r-1-0': nodes[1].style!,
        'branch-l-1-0': nodes[2].style!,
      },
    })
    expect(result).toBeTruthy()
    if (!result) throw new Error('expected insert result')
    expect(result.seededStyle.backgroundColor).toBe('#dbeafe')
    expect(result.seededStyle.borderColor).toBe('#0f766e')
    expect(result.seededStyle.nodeShape).toBe('oval')
    expect(result.seededStyle.backgroundColor).not.toBe('#ff0000')
  })

  it('supports after_node_id and insert_index under parent', () => {
    const { nodes, connections } = sampleGraph()
    const byAfter = insertMindMapSiblingInPlace(nodes, connections, {
      text: 'After A',
      afterNodeId: 'branch-r-1-0',
    })
    expect(byAfter).toBeTruthy()
    if (!byAfter) {
      throw new Error('expected insert result for afterNodeId')
    }
    const targetsAfter = byAfter.connections
      .filter((c) => c.source === 'topic')
      .map((c) => c.target)
    expect(targetsAfter[1]).toBe(byAfter.newNodeId)

    const byIndex = insertMindMapSiblingInPlace(nodes, connections, {
      text: 'At 0',
      parentId: 'topic',
      insertIndex: 0,
    })
    expect(byIndex).toBeTruthy()
    if (!byIndex) {
      throw new Error('expected insert result for insertIndex')
    }
    const targetsIndex = byIndex.connections
      .filter((c) => c.source === 'topic')
      .map((c) => c.target)
    expect(targetsIndex[0]).toBe(byIndex.newNodeId)
  })

  it('L1 Enter on left ignores right-side neighbors for Y and connection order', () => {
    const nodes: DiagramNode[] = [
      {
        id: 'topic',
        text: '中心主题',
        type: 'topic',
        position: { x: 400, y: 300 },
        data: { estimatedWidth: 100, estimatedHeight: 40 },
      },
      {
        id: 'branch-r-1-0',
        text: '分支1',
        type: 'branch',
        position: { x: 560, y: 220 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
      {
        id: 'branch-r-1-1',
        text: '分支2',
        type: 'branch',
        position: { x: 560, y: 360 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
      {
        id: 'branch-l-1-0',
        text: '分支4',
        type: 'branch',
        position: { x: 200, y: 180 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
      {
        id: 'branch-l-1-1',
        text: '子项4.1',
        type: 'branch',
        position: { x: 80, y: 160 },
        data: { estimatedWidth: 70, estimatedHeight: 28 },
      },
      {
        id: 'branch-l-1-2',
        text: '子项4.2',
        type: 'branch',
        position: { x: 80, y: 200 },
        data: { estimatedWidth: 70, estimatedHeight: 28 },
      },
      {
        id: 'branch-l-1-3',
        text: '分支3',
        type: 'branch',
        position: { x: 200, y: 400 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
    ]
    const connections: Connection[] = [
      { id: 'er0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'er1', source: 'topic', target: 'branch-r-1-1' },
      { id: 'el0', source: 'topic', target: 'branch-l-1-0' },
      { id: 'el0a', source: 'branch-l-1-0', target: 'branch-l-1-1' },
      { id: 'el0b', source: 'branch-l-1-0', target: 'branch-l-1-2' },
      { id: 'el3', source: 'topic', target: 'branch-l-1-3' },
    ]

    const result = insertMindMapSiblingInPlace(nodes, connections, {
      anchorNodeId: 'branch-l-1-0',
      text: '新分支',
      position: 'below',
    })
    expect(result).toBeTruthy()
    if (!result) {
      throw new Error('expected insert result for L1 Enter below')
    }

    const leftTargets = topicTargets(result.connections, result.nodes, 'left')
    expect(leftTargets).toEqual(['branch-l-1-0', result.newNodeId, 'branch-l-1-3'])

    const rightTargets = topicTargets(result.connections, result.nodes, 'right')
    expect(rightTargets).toEqual(['branch-r-1-0', 'branch-r-1-1'])

    const created = result.nodes.find((n) => n.id === result.newNodeId)
    const branch3 = result.nodes.find((n) => n.id === 'branch-l-1-3')
    const branch4 = result.nodes.find((n) => n.id === 'branch-l-1-0')
    const topic = result.nodes.find((n) => n.id === 'topic')
    // Enter order: new sibling between 分支4 and 分支3; whole left pack may
    // rigid-slide to center on the topic (absolute Y is not frozen).
    expect(created?.position?.y).toBeGreaterThan(branch4?.position?.y ?? Number.NaN)
    expect(branch3?.position?.y).toBeGreaterThan(created?.position?.y ?? Number.NaN)
    if (!branch4?.position || !created?.position || !branch3?.position || !topic?.position) {
      throw new Error('expected node positions for left pack centering')
    }
    const leftAnchors = [branch4, created, branch3].map(
      (n) => n.position.y + ((n.data?.estimatedHeight as number) ?? 36) / 2
    )
    const leftMid = (Math.min(...leftAnchors) + Math.max(...leftAnchors)) / 2
    const topicCenter = topic.position.y + 20
    expect(leftMid).toBeCloseTo(topicCenter, 0)
  })

  it('L1 Enter above first left does not use right-side prev for placement', () => {
    const nodes: DiagramNode[] = [
      {
        id: 'topic',
        text: '中心主题',
        type: 'topic',
        position: { x: 400, y: 300 },
        data: { estimatedWidth: 100, estimatedHeight: 40 },
      },
      {
        id: 'branch-r-1-0',
        text: '分支1',
        type: 'branch',
        position: { x: 560, y: 360 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
      {
        id: 'branch-l-1-0',
        text: '分支4',
        type: 'branch',
        position: { x: 200, y: 180 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
      {
        id: 'branch-l-1-1',
        text: '分支3',
        type: 'branch',
        position: { x: 200, y: 400 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
    ]
    const connections: Connection[] = [
      { id: 'er0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'el0', source: 'topic', target: 'branch-l-1-0' },
      { id: 'el1', source: 'topic', target: 'branch-l-1-1' },
    ]

    const result = insertMindMapSiblingInPlace(nodes, connections, {
      anchorNodeId: 'branch-l-1-0',
      text: '新分支',
      position: 'above',
    })
    expect(result).toBeTruthy()
    if (!result) {
      throw new Error('expected insert result for L1 Enter above')
    }

    const leftTargets = topicTargets(result.connections, result.nodes, 'left')
    expect(leftTargets[0]).toBe(result.newNodeId)
    expect(leftTargets).toContain('branch-l-1-0')

    const created = result.nodes.find((n) => n.id === result.newNodeId)
    // Must sit above 分支4, not under the right branch at y=360.
    expect(created?.position?.y).toBeLessThan(180)
  })

  it('repeated Enter-below packs new L1s under the left subtree (not topic center)', () => {
    let nodes: DiagramNode[] = [
      {
        id: 'topic',
        text: '中心主题',
        type: 'topic',
        position: { x: 400, y: 300 },
        data: { estimatedWidth: 100, estimatedHeight: 40 },
      },
      {
        id: 'branch-r-1-0',
        text: '分支1',
        type: 'branch',
        position: { x: 560, y: 220 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
      {
        id: 'branch-l-1-0',
        text: '分支4',
        type: 'branch',
        position: { x: 200, y: 180 },
        data: {
          estimatedWidth: 90,
          estimatedHeight: 36,
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-l4',
        },
      },
      {
        id: 'branch-l-2-0',
        text: '子项4.1',
        type: 'branch',
        position: { x: 80, y: 160 },
        data: { estimatedWidth: 70, estimatedHeight: 28 },
      },
      {
        id: 'branch-l-2-1',
        text: '子项4.2',
        type: 'branch',
        position: { x: 80, y: 200 },
        data: { estimatedWidth: 70, estimatedHeight: 28 },
      },
      {
        id: 'branch-l-1-1',
        text: '分支3',
        type: 'branch',
        position: { x: 200, y: 400 },
        data: {
          estimatedWidth: 90,
          estimatedHeight: 36,
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-l3',
        },
      },
    ]
    let connections: Connection[] = [
      { id: 'er0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'el0', source: 'topic', target: 'branch-l-1-0' },
      { id: 'el0a', source: 'branch-l-1-0', target: 'branch-l-2-0' },
      { id: 'el0b', source: 'branch-l-1-0', target: 'branch-l-2-1' },
      { id: 'el1', source: 'topic', target: 'branch-l-1-1' },
    ]

    const createdYs: number[] = []
    let cursor = 'branch-l-1-0'
    for (let i = 0; i < 4; i++) {
      const result = insertMindMapSiblingInPlace(nodes, connections, {
        anchorNodeId: cursor,
        text: `新分支${i}`,
        position: 'below',
      })
      expect(result).toBeTruthy()
      if (!result) {
        throw new Error('expected insert result for repeated Enter-below')
      }
      nodes = result.nodes
      connections = result.connections
      cursor = result.newNodeId
      const y = nodes.find((n) => n.id === cursor)?.position?.y ?? NaN
      createdYs.push(y)
    }

    // Stacked downward in Enter order; pack may rigid-center on the topic.
    for (let i = 1; i < createdYs.length; i++) {
      const curr = createdYs[i]
      const prev = createdYs[i - 1]
      expect(curr).toBeDefined()
      expect(prev).toBeDefined()
      if (curr === undefined || prev === undefined) {
        throw new Error('expected created Y values')
      }
      expect(curr).toBeGreaterThan(prev)
    }
    const branch4Y = nodes.find((n) => n.id === 'branch-l-1-0')?.position?.y ?? 0
    expect(createdYs[0]).toBeGreaterThan(branch4Y)
    const leftL1 = nodes.filter(
      (n) =>
        n.position &&
        isMindMapL1(n.id, connections) &&
        mindMapNodeSide(n.id, { nodes, connections }) === 'left'
    )
    const leftAnchors = leftL1.map(
      (n) => (n.position?.y ?? 0) + ((n.data?.estimatedHeight as number) ?? 36) / 2
    )
    const leftMid = (Math.min(...leftAnchors) + Math.max(...leftAnchors)) / 2
    const topicY = nodes.find((n) => n.id === 'topic')?.position?.y ?? 300
    expect(leftMid).toBeCloseTo(topicY + 20, 0)
  })

  it('Enter on L1 / L2 / L3 inserts a same-level sibling below the selection', () => {
    const nodes: DiagramNode[] = [
      {
        id: 'topic',
        text: '中心主题',
        type: 'topic',
        position: { x: 400, y: 300 },
        data: { estimatedWidth: 100, estimatedHeight: 40 },
      },
      {
        id: 'branch-r-1-0',
        text: '分支1',
        type: 'branch',
        position: { x: 560, y: 200 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
      {
        id: 'branch-r-1-1',
        text: '分支2',
        type: 'branch',
        position: { x: 560, y: 360 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
      {
        id: 'branch-r-2-0',
        text: '子项1.1',
        type: 'branch',
        position: { x: 700, y: 180 },
        data: { estimatedWidth: 70, estimatedHeight: 28 },
      },
      {
        id: 'branch-r-2-1',
        text: '子项1.2',
        type: 'branch',
        position: { x: 700, y: 220 },
        data: { estimatedWidth: 70, estimatedHeight: 28 },
      },
      {
        id: 'branch-r-3-0',
        text: '孙项1.1.1',
        type: 'branch',
        position: { x: 820, y: 170 },
        data: { estimatedWidth: 60, estimatedHeight: 24 },
      },
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-r-1-1' },
      { id: 'c2', source: 'branch-r-1-0', target: 'branch-r-2-0' },
      { id: 'c3', source: 'branch-r-1-0', target: 'branch-r-2-1' },
      { id: 'c4', source: 'branch-r-2-0', target: 'branch-r-3-0' },
    ]

    // L1 selected → new L1 below (sibling under topic).
    const l1 = insertMindMapSiblingInPlace(nodes, connections, {
      anchorNodeId: 'branch-r-1-0',
      text: '新分支',
      position: 'below',
    })
    expect(l1).toBeTruthy()
    if (!l1) {
      throw new Error('expected L1 insert result')
    }
    expect(l1.newNodeId).toMatch(IDENTITY_ID_RE)
    expect(l1.connections.filter((c) => c.source === 'topic').map((c) => c.target)).toEqual([
      'branch-r-1-0',
      l1.newNodeId,
      'branch-r-1-1',
    ])

    // L2 selected → new L2 below (grandchild of topic, sibling under 分支1).
    const l2 = insertMindMapSiblingInPlace(nodes, connections, {
      anchorNodeId: 'branch-r-2-0',
      text: '新子项',
      position: 'below',
    })
    expect(l2).toBeTruthy()
    if (!l2) {
      throw new Error('expected L2 insert result')
    }
    expect(l2.newNodeId).toMatch(IDENTITY_ID_RE)
    expect(l2.connections.filter((c) => c.source === 'branch-r-1-0').map((c) => c.target)).toEqual([
      'branch-r-2-0',
      l2.newNodeId,
      'branch-r-2-1',
    ])

    // L3 selected → new L3 below (sibling under 子项1.1).
    const l3 = insertMindMapSiblingInPlace(nodes, connections, {
      anchorNodeId: 'branch-r-3-0',
      text: '新孙项',
      position: 'below',
    })
    expect(l3).toBeTruthy()
    if (!l3) {
      throw new Error('expected L3 insert result')
    }
    expect(l3.newNodeId).toMatch(IDENTITY_ID_RE)
    expect(l3.connections.filter((c) => c.source === 'branch-r-2-0').map((c) => c.target)).toEqual([
      'branch-r-3-0',
      l3.newNodeId,
    ])
  })

  it('Enter on a right L1 inserts on the right, not the left', () => {
    const { nodes, connections } = sampleGraph()
    // Add a left L1 so a wrong-side bug would be visible.
    const withLeft: DiagramNode[] = [
      ...nodes,
      {
        id: 'branch-l-1-0',
        text: '左分支',
        type: 'branch',
        position: { x: 200, y: 280 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
    ]
    const withLeftConns: Connection[] = [
      ...connections,
      {
        id: 'edge-topic-branch-l-1-0',
        source: 'topic',
        target: 'branch-l-1-0',
        sourceHandle: 'mindmap-left',
        targetHandle: 'right-target',
      },
    ]

    const result = insertMindMapSiblingInPlace(withLeft, withLeftConns, {
      anchorNodeId: 'branch-r-1-0',
      text: '新分支',
      position: 'below',
    })
    expect(result).toBeTruthy()
    if (!result) {
      throw new Error('expected insert result for right L1 Enter')
    }
    expect(result.newNodeId).toMatch(IDENTITY_ID_RE)
    expect(result.connections.filter((c) => c.source === 'topic').map((c) => c.target)).toEqual([
      'branch-r-1-0',
      result.newNodeId,
      'branch-r-1-1',
      'branch-l-1-0',
    ])
  })

  it('batch L2 sibling inserts (Kitty/paste sync loop) keep distinct Y positions', () => {
    // Mimic applyVoiceDiagramAddNodes / multiline paste: several siblings in one tick
    // before rAF layout. Insert-local settle must keep store Y usable between loops.
    let nodes: DiagramNode[] = [
      {
        id: 'topic',
        text: '主题',
        type: 'topic',
        position: { x: 400, y: 300 },
        data: { estimatedWidth: 80, estimatedHeight: 40 },
      },
      {
        id: 'branch-r-1-0',
        text: '分支',
        type: 'branch',
        position: { x: 520, y: 300 },
        data: {
          estimatedWidth: 90,
          estimatedHeight: 36,
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-parent',
        },
      },
      {
        id: 'branch-r-2-0',
        text: '子项',
        type: 'branch',
        position: { x: 640, y: 300 },
        data: {
          estimatedWidth: 70,
          estimatedHeight: 28,
          [MINDMAP_NODE_UID_DATA_KEY]: 'uid-child0',
        },
      },
    ]
    let connections: Connection[] = [
      {
        id: 'c0',
        source: 'topic',
        target: 'branch-r-1-0',
        sourceHandle: 'mindmap-right',
        targetHandle: 'left',
      },
      {
        id: 'c1',
        source: 'branch-r-1-0',
        target: 'branch-r-2-0',
        sourceHandle: 'right',
        targetHandle: 'left',
      },
    ]

    const insertedIds: string[] = ['branch-r-2-0']
    let anchor = 'branch-r-2-0'
    for (let i = 0; i < 3; i++) {
      const result = insertMindMapSiblingInPlace(nodes, connections, {
        anchorNodeId: anchor,
        text: `批量子项${i}`,
        position: 'below',
        diagramStyleId: 'classic',
      })
      expect(result).toBeTruthy()
      if (!result) {
        throw new Error('expected insert result for batch L2 siblings')
      }
      nodes = result.nodes
      connections = result.connections
      insertedIds.push(result.newNodeId)
      anchor = result.newNodeId
    }

    const ys = insertedIds.map((id) => nodes.find((n) => n.id === id)?.position?.y ?? Number.NaN)
    expect(ys.every((y) => Number.isFinite(y))).toBe(true)
    for (let i = 1; i < ys.length; i++) {
      const curr = ys[i]
      const prev = ys[i - 1]
      expect(curr).toBeDefined()
      expect(prev).toBeDefined()
      if (curr === undefined || prev === undefined) {
        throw new Error('expected batch insert Y values')
      }
      expect(curr).toBeGreaterThan(prev)
    }
  })

  it('Enter below L2 uses parent depth+1 even if a sibling id depth is stale', () => {
    // Structural L2 whose id wrongly says depth 1 — new sibling must still be depth 2.
    const nodes: DiagramNode[] = [
      {
        id: 'topic',
        text: '主题',
        type: 'topic',
        position: { x: 400, y: 300 },
        data: { estimatedWidth: 80, estimatedHeight: 40 },
      },
      {
        id: 'branch-l-1-0',
        text: '分支',
        type: 'branch',
        position: { x: 200, y: 300 },
        data: { estimatedWidth: 90, estimatedHeight: 36 },
      },
      {
        id: 'branch-l-1-9',
        text: '错深度子项',
        type: 'branch',
        position: { x: 80, y: 300 },
        data: { estimatedWidth: 70, estimatedHeight: 28 },
      },
    ]
    const connections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-l-1-0' },
      { id: 'c1', source: 'branch-l-1-0', target: 'branch-l-1-9' },
    ]

    const result = insertMindMapSiblingInPlace(nodes, connections, {
      anchorNodeId: 'branch-l-1-9',
      text: '新子项',
      position: 'below',
    })
    expect(result).toBeTruthy()
    if (!result) {
      throw new Error('expected insert result for stale-depth L2')
    }
    expect(result.newNodeId).toMatch(IDENTITY_ID_RE)
    expect(result.connections.find((c) => c.target === result.newNodeId)?.source).toBe(
      'branch-l-1-0'
    )
  })
})
