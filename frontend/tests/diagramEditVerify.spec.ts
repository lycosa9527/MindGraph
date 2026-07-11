// Diagram Edit Tool tests
import { describe, expect, it } from 'vitest'

import {
  captureDiagramFingerprint,
  resolveCreatedNodeIds,
  verifyMindMapEffect,
} from '@/utils/diagramEditVerify'

describe('diagramEditVerify', () => {
  it('resolves created node ids from before/after diff', () => {
    const before = captureDiagramFingerprint(
      [{ id: 'topic', type: 'topic', text: 'Cars', position: { x: 0, y: 0 } }],
      []
    )
    const after = captureDiagramFingerprint(
      [
        { id: 'topic', type: 'topic', text: 'Cars', position: { x: 0, y: 0 } },
        { id: 'branch-r-1-0', text: 'DIY', position: { x: 0, y: 0 } },
      ],
      [{ source: 'topic', target: 'branch-r-1-0' }]
    )
    expect(
      resolveCreatedNodeIds(before, after, { op: 'add_branch', text: 'DIY' })
    ).toEqual(['branch-r-1-0'])
  })

  it('verifies add_branch with topic edge', () => {
    const before = captureDiagramFingerprint(
      [{ id: 'topic', type: 'topic', text: 'Cars', position: { x: 0, y: 0 } }],
      []
    )
    const after = captureDiagramFingerprint(
      [
        { id: 'topic', type: 'topic', text: 'Cars', position: { x: 0, y: 0 } },
        { id: 'branch-r-1-0', text: 'DIY', position: { x: 0, y: 0 } },
      ],
      [{ source: 'topic', target: 'branch-r-1-0' }]
    )
    const report = verifyMindMapEffect(
      { op: 'add_branch', text: 'DIY', parent_ref: 'topic' },
      after,
      before.nodes.length
    )
    expect(report.ok).toBe(true)
    expect(before.nodes).toHaveLength(1)
  })

  it('fails when parent edge missing', () => {
    const after = captureDiagramFingerprint(
      [
        { id: 'topic', type: 'topic', text: 'Cars', position: { x: 0, y: 0 } },
        { id: 'branch-r-1-0', text: 'DIY', position: { x: 0, y: 0 } },
      ],
      []
    )
    const report = verifyMindMapEffect(
      { op: 'add_branch', text: 'DIY', parent_ref: 'topic' },
      after,
      1
    )
    expect(report.ok).toBe(false)
  })

  it('verifies add_child under named parent_ref', () => {
    const before = captureDiagramFingerprint(
      [
        { id: 'topic', type: 'topic', text: '鼠标', position: { x: 0, y: 0 } },
        { id: 'branch-r-1-0', text: '品牌', position: { x: 0, y: 0 } },
      ],
      [{ source: 'topic', target: 'branch-r-1-0' }]
    )
    const after = captureDiagramFingerprint(
      [
        { id: 'topic', type: 'topic', text: '鼠标', position: { x: 0, y: 0 } },
        { id: 'branch-r-1-0', text: '品牌', position: { x: 0, y: 0 } },
        { id: 'branch-r-1-0-0', text: '罗技', position: { x: 0, y: 0 } },
      ],
      [
        { source: 'topic', target: 'branch-r-1-0' },
        { source: 'branch-r-1-0', target: 'branch-r-1-0-0' },
      ]
    )
    const report = verifyMindMapEffect(
      { op: 'add_child', text: '罗技', parent_ref: '品牌' },
      after,
      before.nodes.length
    )
    expect(report.ok).toBe(true)
  })

  it('fails add_child when attached under wrong parent', () => {
    const after = captureDiagramFingerprint(
      [
        { id: 'topic', type: 'topic', text: '鼠标', position: { x: 0, y: 0 } },
        { id: 'branch-r-1-0', text: '品牌', position: { x: 0, y: 0 } },
        { id: 'branch-r-1-1', text: '罗技', position: { x: 0, y: 0 } },
      ],
      [
        { source: 'topic', target: 'branch-r-1-0' },
        { source: 'topic', target: 'branch-r-1-1' },
      ]
    )
    const report = verifyMindMapEffect(
      { op: 'add_child', text: '罗技', parent_ref: '品牌' },
      after,
      2
    )
    expect(report.ok).toBe(false)
  })
})
