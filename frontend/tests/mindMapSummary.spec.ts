import { describe, expect, it } from 'vitest'

import type { Connection, DiagramNode } from '@/types'
import {
  areConsecutiveSiblingPaths,
  coveredPathsFromVerticalRange,
  mindMapSummaryChildNodeId,
  mindMapSummaryRootNodeId,
  parseMindMapSummaries,
  parseMindMapSummaryNodeId,
  remapSummaryCoveredPaths,
  resolveConsecutiveSiblingRange,
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
