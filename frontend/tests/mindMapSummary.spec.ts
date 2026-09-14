import { describe, expect, it } from 'vitest'

import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import {
  coveredBoxesForSummary,
  mindMapSummaryOutwardRangeRect,
  placeMindMapSummaryNodes,
} from '@/stores/diagram/mindMapSummaryLayout'
import type { Connection, DiagramNode } from '@/types'
import {
  areConsecutiveSiblingPaths,
  coveredPathsFromVerticalRange,
  expandSummaryRangePaths,
  isMindMapSummaryExtentPath,
  mindMapSummaryChildNodeId,
  mindMapSummaryRootNodeId,
  parseMindMapSummaries,
  parseMindMapSummaryNodeId,
  remapSummaryCoveredPaths,
  resolveConsecutiveSiblingRange,
  resolveMindMapSummaryInsertRange,
  siblingPathsSharingParent,
} from '@/utils/mindMapSummary'
import { mindMapSummaryBracePath, mindMapSummaryConnectorPath } from '@/utils/mindMapSummaryBrace'

const nodes: DiagramNode[] = [
  { id: 'topic', text: 'T', type: 'topic' },
  { id: 'a', text: 'A', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 1 } },
  { id: 'b', text: 'B', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 1 } },
  { id: 'c', text: 'C', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 1 } },
  { id: 'd', text: 'D', type: 'branch', data: { mindMapSide: 'left', mindMapDepth: 1 } },
]

const connections: Connection[] = [
  { id: 'e1', source: 'topic', target: 'a', sourceHandle: 'mindmap-right' },
  { id: 'e2', source: 'topic', target: 'b', sourceHandle: 'mindmap-right' },
  { id: 'e3', source: 'topic', target: 'c', sourceHandle: 'mindmap-right' },
  { id: 'e4', source: 'topic', target: 'd', sourceHandle: 'mindmap-left' },
]

describe('mind map summary range', () => {
  it('accepts one node or consecutive siblings', () => {
    expect(resolveConsecutiveSiblingRange(['a'], nodes, connections)).toEqual({
      ok: true,
      coveredPaths: ['r/0'],
    })
    expect(resolveConsecutiveSiblingRange(['a', 'b', 'c'], nodes, connections)).toEqual({
      ok: true,
      coveredPaths: ['r/0', 'r/1', 'r/2'],
    })
  })

  it('rejects mixed parents and gaps', () => {
    expect(resolveConsecutiveSiblingRange(['a', 'd'], nodes, connections).ok).toBe(false)
    expect(resolveConsecutiveSiblingRange(['a', 'c'], nodes, connections).reason).toBe(
      'not-consecutive'
    )
    expect(resolveConsecutiveSiblingRange(['topic'], nodes, connections).reason).toBe('topic')
  })

  it('covers every direct child when inserting on a branch', () => {
    const tree: DiagramNode[] = [
      ...nodes,
      { id: 'a0', text: 'A0', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 2 } },
      { id: 'a1', text: 'A1', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 2 } },
      { id: 'a2', text: 'A2', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 2 } },
    ]
    const links: Connection[] = [
      ...connections,
      { id: 'e5', source: 'a', target: 'a0', sourceHandle: 'mindmap-right' },
      { id: 'e6', source: 'a', target: 'a1', sourceHandle: 'mindmap-right' },
      { id: 'e7', source: 'a', target: 'a2', sourceHandle: 'mindmap-right' },
    ]
    expect(resolveMindMapSummaryInsertRange(['a'], tree, links)).toEqual({
      ok: true,
      coveredPaths: ['r/0/0', 'r/0/1', 'r/0/2'],
    })
    expect(resolveMindMapSummaryInsertRange(['a', 'a0'], tree, links)).toEqual({
      ok: true,
      coveredPaths: ['r/0/0', 'r/0/1', 'r/0/2'],
    })
    expect(resolveMindMapSummaryInsertRange(['a0'], tree, links)).toEqual({
      ok: true,
      coveredPaths: ['r/0/0'],
    })
    expect(resolveMindMapSummaryInsertRange(['a0', 'a1'], tree, links)).toEqual({
      ok: true,
      coveredPaths: ['r/0/0', 'r/0/1'],
    })
    expect(resolveMindMapSummaryInsertRange(['b'], tree, links)).toEqual({
      ok: true,
      coveredPaths: ['r/1'],
    })
    expect(resolveMindMapSummaryInsertRange(['topic'], tree, links).reason).toBe('topic')
  })

  it('wraps the parent branch when 概要 already covers every child', () => {
    const tree: DiagramNode[] = [
      ...nodes,
      { id: 'a0', text: 'A0', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 2 } },
      { id: 'a1', text: 'A1', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 2 } },
      { id: 'a2', text: 'A2', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 2 } },
    ]
    const links: Connection[] = [
      ...connections,
      { id: 'e5', source: 'a', target: 'a0', sourceHandle: 'mindmap-right' },
      { id: 'e6', source: 'a', target: 'a1', sourceHandle: 'mindmap-right' },
      { id: 'e7', source: 'a', target: 'a2', sourceHandle: 'mindmap-right' },
    ]
    expect(expandSummaryRangePaths(['r/0/0', 'r/0/1', 'r/0/2'], tree, links)).toEqual([
      'r/0',
      'r/0/0',
      'r/0/1',
      'r/0/2',
    ])
    expect(expandSummaryRangePaths(['r/0/0', 'r/0/1'], tree, links)).toEqual(['r/0/0', 'r/0/1'])
    expect(expandSummaryRangePaths(['r/0/0'], tree, links)).toEqual(['r/0/0'])
    expect(expandSummaryRangePaths(['r/0', 'r/1', 'r/2'], tree, links)).toEqual([
      'r/0',
      'r/1',
      'r/2',
    ])
  })

  it('walks up through a single-child ancestor chain', () => {
    const tree: DiagramNode[] = [
      ...nodes,
      { id: 'a0', text: 'A0', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 2 } },
      { id: 'a00', text: 'A00', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 3 } },
      { id: 'a01', text: 'A01', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 3 } },
    ]
    const links: Connection[] = [
      ...connections,
      { id: 'e5', source: 'a', target: 'a0', sourceHandle: 'mindmap-right' },
      { id: 'e6', source: 'a0', target: 'a00', sourceHandle: 'mindmap-right' },
      { id: 'e7', source: 'a0', target: 'a01', sourceHandle: 'mindmap-right' },
    ]
    expect(expandSummaryRangePaths(['r/0/0/0', 'r/0/0/1'], tree, links)).toEqual([
      'r/0',
      'r/0/0',
      'r/0/0/0',
      'r/0/0/1',
    ])
  })

  it('keeps only a consecutive run after a covered child is deleted', () => {
    const remapped = remapSummaryCoveredPaths(
      ['r/0', 'r/1', 'r/2'],
      nodes,
      connections,
      nodes.filter((n) => n.id !== 'b'),
      connections.filter((c) => c.target !== 'b'),
      (oldId, _oN, _oC, newNodes) => (newNodes.some((n) => n.id === oldId) ? oldId : null)
    )
    expect(areConsecutiveSiblingPaths(remapped)).toBe(true)
    expect(remapped).toEqual(['r/0', 'r/1'])
  })

  it('treats descendant paths as part of the covered extent', () => {
    expect(isMindMapSummaryExtentPath('r/0', ['r/0'])).toBe(true)
    expect(isMindMapSummaryExtentPath('r/0/1', ['r/0'])).toBe(true)
    expect(isMindMapSummaryExtentPath('r/0/1/2', ['r/0'])).toBe(true)
    expect(isMindMapSummaryExtentPath('r/1', ['r/0'])).toBe(false)
    expect(isMindMapSummaryExtentPath('r/00', ['r/0'])).toBe(false)
  })

  it('lists every sibling that shares the covered parent', () => {
    expect(siblingPathsSharingParent(['r/1'], nodes, connections)).toEqual(['r/0', 'r/1', 'r/2'])
    expect(siblingPathsSharingParent(['l/3'], nodes, connections)).toEqual(['l/3'])
  })

  it('includes siblings whose centers fall in the dragged vertical range', () => {
    const slots = [
      { path: 'r/0', y: 0, height: 30 },
      { path: 'r/1', y: 40, height: 30 },
      { path: 'r/2', y: 80, height: 30 },
    ]
    expect(coveredPathsFromVerticalRange(slots, -6, 36)).toEqual(['r/0'])
    expect(coveredPathsFromVerticalRange(slots, -6, 76)).toEqual(['r/0', 'r/1'])
    expect(coveredPathsFromVerticalRange(slots, 50, 130)).toEqual(['r/1', 'r/2'])
    expect(coveredPathsFromVerticalRange(slots, 200, 220)).toEqual(['r/2'])
  })
})

describe('mind map summary chrome', () => {
  it('keeps valid chrome fields and drops invalid ones', () => {
    const parsed = parseMindMapSummaries([
      {
        id: 's1',
        text: '概要',
        coveredPaths: ['r/0'],
        kind: 'bracket',
        lineStyle: 'dashed',
        strokeColor: '#c2410c',
        strokeWidth: 3,
      },
      {
        id: 's2',
        text: 'bad',
        coveredPaths: ['r/1'],
        kind: 'star',
        lineStyle: 'wavy',
        strokeColor: 'red',
        strokeWidth: 99,
      },
    ])
    expect(parsed[0]).toMatchObject({
      kind: 'bracket',
      lineStyle: 'dashed',
      strokeColor: '#c2410c',
      strokeWidth: 3,
    })
    expect(parsed[1]?.kind).toBeUndefined()
    expect(parsed[1]?.lineStyle).toBeUndefined()
    expect(parsed[1]?.strokeColor).toBeUndefined()
    expect(parsed[1]?.strokeWidth).toBeUndefined()
  })
})

describe('mind map summary ids', () => {
  it('round-trips root and child ids', () => {
    const root = mindMapSummaryRootNodeId('abc')
    expect(parseMindMapSummaryNodeId(root)).toEqual({ summaryId: 'abc', childPath: [] })
    const child = mindMapSummaryChildNodeId('abc', [0, 1])
    expect(parseMindMapSummaryNodeId(child)).toEqual({ summaryId: 'abc', childPath: [0, 1] })
  })
})

describe('mind map summary brace', () => {
  it('builds a right-side brace, range rect, and handle above the tip', () => {
    const path = mindMapSummaryBracePath(
      [
        { x: 0, y: 0, width: 80, height: 30 },
        { x: 0, y: 40, width: 80, height: 30 },
      ],
      'right'
    )
    expect(path).not.toBeNull()
    expect(path?.tipX).toBeGreaterThan(80)
    expect(path?.bracePath.includes('Q')).toBe(true)
    expect(path?.rangeRect.width).toBeGreaterThan(80)
    expect(path?.handleY).toBeLessThan(path?.tipY ?? 0)
    expect(path?.handleX).toBeLessThan(path?.tipX ?? 0)
  })

  it('draws a bracket without curves and a paren with cubics', () => {
    const boxes = [
      { x: 0, y: 0, width: 80, height: 30 },
      { x: 0, y: 40, width: 80, height: 30 },
    ]
    const bracket = mindMapSummaryBracePath(boxes, 'right', { kind: 'bracket' })
    const paren = mindMapSummaryBracePath(boxes, 'right', { kind: 'paren' })
    expect(bracket?.bracePath.includes('Q')).toBe(false)
    expect(bracket?.bracePath.includes('L')).toBe(true)
    expect(paren?.bracePath.includes('C')).toBe(true)
  })

  it('stretches the brace to an explicit range rectangle', () => {
    const boxes = [{ x: 0, y: 0, width: 80, height: 30 }]
    const stretched = mindMapSummaryBracePath(boxes, 'right', {
      rangeRect: { x: -6, y: -6, width: 92, height: 200 },
    })
    expect(stretched?.rangeRect.height).toBe(200)
    expect(stretched?.bracePath.includes('194')).toBe(true)
  })

  it('stops the connector before the summary node', () => {
    const line = mindMapSummaryConnectorPath(
      100,
      40,
      { x: 130, y: 20, width: 80, height: 40 },
      'right'
    )
    expect(line.includes('130')).toBe(false)
    expect(line.startsWith('M 100 40')).toBe(true)
  })
})

describe('mind map summary placement', () => {
  it('extends the range past descendant topics without changing sibling height', () => {
    const siblings = [{ x: 100, y: 40, width: 80, height: 30 }]
    const extent = [
      { x: 100, y: 40, width: 80, height: 30 },
      { x: 250, y: 10, width: 80, height: 30 },
    ]
    const range = mindMapSummaryOutwardRangeRect(siblings, extent, 'right')
    expect(range).not.toBeNull()
    expect(range?.y).toBe(34)
    expect(range?.height).toBe(42)
    expect(range && range.x + range.width).toBeGreaterThan(330)
  })

  it('includes the parent branch box when every child is covered', () => {
    const tree: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic', position: { x: 0, y: 100 } },
      {
        id: 'a',
        text: 'A',
        type: 'branch',
        position: { x: 100, y: 80 },
        data: { mindMapSide: 'right', mindMapDepth: 1 },
      },
      {
        id: 'a0',
        text: 'A0',
        type: 'branch',
        position: { x: 250, y: 40 },
        data: { mindMapSide: 'right', mindMapDepth: 2 },
      },
      {
        id: 'a1',
        text: 'A1',
        type: 'branch',
        position: { x: 250, y: 80 },
        data: { mindMapSide: 'right', mindMapDepth: 2 },
      },
    ]
    const links: Connection[] = [
      { id: 'e1', source: 'topic', target: 'a', sourceHandle: 'mindmap-right' },
      { id: 'e2', source: 'a', target: 'a0', sourceHandle: 'mindmap-right' },
      { id: 'e3', source: 'a', target: 'a1', sourceHandle: 'mindmap-right' },
    ]
    const widths = { a: 80, a0: 80, a1: 80 }
    const heights = { a: 30, a0: 30, a1: 30 }
    const boxes = coveredBoxesForSummary(
      tree,
      links,
      { id: 's1', text: '概要', coveredPaths: ['r/0/0', 'r/0/1'] },
      widths,
      heights
    )
    expect(boxes.some((box) => box.x === 100 && box.y === 80)).toBe(true)
    const partial = coveredBoxesForSummary(
      tree,
      links,
      { id: 's2', text: '概要', coveredPaths: ['r/0/0'] },
      widths,
      heights
    )
    expect(partial.some((box) => box.x === 100 && box.y === 80)).toBe(false)
  })

  it('does not shrink the range from leftover node.style width after a color persist', () => {
    const tree: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic', position: { x: 0, y: 100 } },
      {
        id: 'a',
        text: 'A',
        type: 'branch',
        position: { x: 100, y: 80 },
        style: { width: 10, height: 4, textColor: '#e11d48' },
        data: { mindMapSide: 'right', mindMapDepth: 1 },
      },
    ]
    const links: Connection[] = [
      { id: 'e1', source: 'topic', target: 'a', sourceHandle: 'mindmap-right' },
    ]
    const measured = coveredBoxesForSummary(
      tree,
      links,
      { id: 's1', text: '概要', coveredPaths: ['r/0'] },
      { a: 160 },
      { a: 36 }
    )
    expect(measured[0]?.width).toBe(160)
    expect(measured[0]?.height).toBe(36)
    const fallback = coveredBoxesForSummary(
      tree,
      links,
      { id: 's1', text: '概要', coveredPaths: ['r/0'] },
      {},
      {}
    )
    expect(fallback[0]?.width).toBe(MIND_MAP_GEOMETRY.minWidth)
    expect(fallback[0]?.height).toBe(MIND_MAP_GEOMETRY.minHeight)
    const liveLeftover = coveredBoxesForSummary(
      tree,
      links,
      { id: 's1', text: '概要', coveredPaths: ['r/0'] },
      { a: 160 },
      { a: 36 },
      ['r/0'],
      new Map([['a', { x: 100, y: 80, width: 10, height: 4 }]])
    )
    expect(liveLeftover[0]?.width).toBe(160)
    expect(liveLeftover[0]?.height).toBe(36)
  })

  it('scrubs leftover layout sizes from _node_styles when placing 概要 nodes', () => {
    const tree: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic', position: { x: 0, y: 100 } },
      {
        id: 'a',
        text: 'A',
        type: 'branch',
        position: { x: 100, y: 80 },
        data: { mindMapSide: 'right', mindMapDepth: 1 },
      },
    ]
    const links: Connection[] = [
      { id: 'e1', source: 'topic', target: 'a', sourceHandle: 'mindmap-right' },
    ]
    const rootId = mindMapSummaryRootNodeId('s1')
    const data = {
      type: 'mindmap' as const,
      nodes: tree,
      connections: links,
      _node_styles: {
        [rootId]: { textColor: '#16a34a', width: 12, height: 8 },
        a: { textColor: '#dc2626', width: 400 },
      },
    }
    tree[1].style = { textColor: '#dc2626', width: 12, height: 8 }
    placeMindMapSummaryNodes(
      tree,
      links,
      [{ id: 's1', text: '概要', coveredPaths: ['r/0'] }],
      data,
      { a: 80, [rootId]: 90 },
      { a: 30, [rootId]: 34 }
    )
    expect(data._node_styles?.[rootId]).toEqual({ textColor: '#16a34a' })
    expect(data._node_styles?.a).toEqual({ textColor: '#dc2626' })
    expect(tree[1].style).toEqual({ textColor: '#dc2626' })
  })

  it('places the 概要 node to the right of covered children', () => {
    const tree: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic', position: { x: 0, y: 100 } },
      {
        id: 'a',
        text: 'A',
        type: 'branch',
        position: { x: 100, y: 80 },
        data: { mindMapSide: 'right', mindMapDepth: 1 },
      },
      {
        id: 'a1',
        text: 'A1',
        type: 'branch',
        position: { x: 250, y: 80 },
        data: { mindMapSide: 'right', mindMapDepth: 2 },
      },
    ]
    const links: Connection[] = [
      { id: 'e1', source: 'topic', target: 'a', sourceHandle: 'mindmap-right' },
      { id: 'e2', source: 'a', target: 'a1', sourceHandle: 'mindmap-right' },
    ]
    const widths = { a: 80, a1: 80, [mindMapSummaryRootNodeId('s1')]: 90 }
    const heights = { a: 30, a1: 30, [mindMapSummaryRootNodeId('s1')]: 34 }
    const placed = placeMindMapSummaryNodes(
      tree,
      links,
      [{ id: 's1', text: '概要', coveredPaths: ['r/0'] }],
      null,
      widths,
      heights
    )
    const root = placed.find((node) => node.id === mindMapSummaryRootNodeId('s1'))
    expect(root?.position?.x).toBeGreaterThan(330)
  })

  it('places a left-side 概要 node past the leftmost descendant', () => {
    const tree: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic', position: { x: 400, y: 100 } },
      {
        id: 'a',
        text: 'A',
        type: 'branch',
        position: { x: 280, y: 80 },
        data: { mindMapSide: 'left', mindMapDepth: 1 },
      },
      {
        id: 'a1',
        text: 'A1',
        type: 'branch',
        position: { x: 120, y: 80 },
        data: { mindMapSide: 'left', mindMapDepth: 2 },
      },
    ]
    const links: Connection[] = [
      { id: 'e1', source: 'topic', target: 'a', sourceHandle: 'mindmap-left' },
      { id: 'e2', source: 'a', target: 'a1', sourceHandle: 'mindmap-left' },
    ]
    const rootId = mindMapSummaryRootNodeId('s1')
    const widths = { a: 80, a1: 80, [rootId]: 90 }
    const heights = { a: 30, a1: 30, [rootId]: 34 }
    const placed = placeMindMapSummaryNodes(
      tree,
      links,
      [{ id: 's1', text: '概要', coveredPaths: ['l/0'] }],
      null,
      widths,
      heights
    )
    const root = placed.find((node) => node.id === rootId)
    expect(root?.position?.x).toBeLessThan(120)
  })

  it('keeps persisted 概要 border, shape, and text color after rematerialize', () => {
    const tree: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic', position: { x: 0, y: 100 } },
      {
        id: 'a',
        text: 'A',
        type: 'branch',
        position: { x: 100, y: 80 },
        data: { mindMapSide: 'right', mindMapDepth: 1 },
      },
    ]
    const links: Connection[] = [
      { id: 'e1', source: 'topic', target: 'a', sourceHandle: 'mindmap-right' },
    ]
    const rootId = mindMapSummaryRootNodeId('s1')
    const childId = mindMapSummaryChildNodeId('s1', [0])
    const widths = { a: 80, [rootId]: 90, [childId]: 70 }
    const heights = { a: 30, [rootId]: 34, [childId]: 28 }
    const placed = placeMindMapSummaryNodes(
      tree,
      links,
      [{ id: 's1', text: '概要', coveredPaths: ['r/0'], children: [{ text: '子题' }] }],
      {
        type: 'mindmap',
        nodes: tree,
        connections: links,
        _node_styles: {
          [rootId]: {
            borderColor: '#dc2626',
            textColor: '#16a34a',
            nodeShape: 'rectangle',
            fontSize: 20,
            width: 12,
            height: 8,
          },
          [childId]: {
            borderColor: '#2563eb',
            textColor: '#7c3aed',
          },
        },
      },
      widths,
      heights
    )
    const root = placed.find((node) => node.id === rootId)
    const child = placed.find((node) => node.id === childId)
    expect(root?.style?.borderColor).toBe('#dc2626')
    expect(root?.style?.textColor).toBe('#16a34a')
    expect(root?.style?.nodeShape).toBe('rectangle')
    expect(root?.style?.fontSize).toBe(20)
    expect(root?.style?.width).toBeUndefined()
    expect(root?.style?.height).toBeUndefined()
    expect(child?.style?.borderColor).toBe('#2563eb')
    expect(child?.style?.textColor).toBe('#7c3aed')
  })
})
