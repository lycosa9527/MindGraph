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
        { id: 'uid-diy', text: 'DIY', position: { x: 0, y: 0 } },
      ],
      [{ source: 'topic', target: 'uid-diy' }]
    )
    expect(
      resolveCreatedNodeIds(before, after, { op: 'add_branch', text: 'DIY' })
    ).toEqual(['uid-diy'])
  })

  it('verifies add_branch with topic edge', () => {
    const before = captureDiagramFingerprint(
      [{ id: 'topic', type: 'topic', text: 'Cars', position: { x: 0, y: 0 } }],
      []
    )
    const after = captureDiagramFingerprint(
      [
        { id: 'topic', type: 'topic', text: 'Cars', position: { x: 0, y: 0 } },
        { id: 'uid-diy', text: 'DIY', position: { x: 0, y: 0 } },
      ],
      [{ source: 'topic', target: 'uid-diy' }]
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
        { id: 'uid-diy', text: 'DIY', position: { x: 0, y: 0 } },
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
        { id: 'uid-brand', text: '品牌', position: { x: 0, y: 0 } },
      ],
      [{ source: 'topic', target: 'uid-brand' }]
    )
    const after = captureDiagramFingerprint(
      [
        { id: 'topic', type: 'topic', text: '鼠标', position: { x: 0, y: 0 } },
        { id: 'uid-brand', text: '品牌', position: { x: 0, y: 0 } },
        { id: 'uid-logitech', text: '罗技', position: { x: 0, y: 0 } },
      ],
      [
        { source: 'topic', target: 'uid-brand' },
        { source: 'uid-brand', target: 'uid-logitech' },
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
        { id: 'uid-brand', text: '品牌', position: { x: 0, y: 0 } },
        { id: 'uid-logitech', text: '罗技', position: { x: 0, y: 0 } },
      ],
      [
        { source: 'topic', target: 'uid-brand' },
        { source: 'topic', target: 'uid-logitech' },
      ]
    )
    const report = verifyMindMapEffect(
      { op: 'add_child', text: '罗技', parent_ref: '品牌' },
      after,
      2
    )
    expect(report.ok).toBe(false)
  })

  it('verifies update_node by UUID when two nodes share the same text', () => {
    const after = captureDiagramFingerprint(
      [
        { id: 'topic', type: 'topic', text: 'Cars', position: { x: 0, y: 0 } },
        { id: 'uid-diy-a', text: 'Paint', position: { x: 0, y: 0 } },
        { id: 'uid-diy-b', text: 'Paint', position: { x: 0, y: 0 } },
      ],
      [
        { source: 'topic', target: 'uid-diy-a' },
        { source: 'topic', target: 'uid-diy-b' },
      ]
    )
    const hit = verifyMindMapEffect(
      { op: 'update_node', node_id: 'uid-diy-b', text: 'Paint' },
      after,
      3
    )
    expect(hit.ok).toBe(true)
    const miss = verifyMindMapEffect(
      { op: 'update_node', node_identifier: 'uid-missing', text: 'Paint' },
      after,
      3
    )
    expect(miss.ok).toBe(false)
  })
})
