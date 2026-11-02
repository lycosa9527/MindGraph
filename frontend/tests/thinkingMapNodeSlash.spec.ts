import { describe, expect, it } from 'vitest'

import {
  readThinkingMapSlashRole,
  resolveThinkingMapNodeSlash,
} from '@/composables/canvasPage/thinkingMapNodeSlash'
import type { Connection, DiagramNode } from '@/types'

function node(id: string, type: DiagramNode['type'], data?: Record<string, unknown>): DiagramNode {
  return { id, text: id, type, position: { x: 0, y: 0 }, data }
}

const FLAT_TYPES = ['circle_map', 'bubble_map', 'bridge_map'] as const

describe('resolveThinkingMapNodeSlash', () => {
  it('adds the only node kind on maps that have no child or sibling split', () => {
    for (const type of FLAT_TYPES) {
      expect(resolveThinkingMapNodeSlash(type, 'sibling', 'peer')).toBe('add_node')
      expect(resolveThinkingMapNodeSlash(type, 'delete', 'topic')).toBe('delete')
    }
  })

  it('adds a tree category on the current level', () => {
    expect(resolveThinkingMapNodeSlash('tree_map', 'sibling', 'topic')).toBe('add_tree_category')
    expect(resolveThinkingMapNodeSlash('tree_map', 'sibling', 'peer')).toBe('add_tree_category')
    expect(resolveThinkingMapNodeSlash('tree_map', 'sibling', 'nested')).toBe('add_child')
    expect(resolveThinkingMapNodeSlash('tree_map', 'delete', 'peer')).toBe('delete')
  })

  it('adds a flow step on the current level and a substep from a nested step', () => {
    expect(resolveThinkingMapNodeSlash('flow_map', 'sibling', 'peer')).toBe('add_node')
    expect(resolveThinkingMapNodeSlash('flow_map', 'sibling', 'nested')).toBe('add_child')
    expect(resolveThinkingMapNodeSlash('flow_map', 'sibling', 'topic')).toBe('add_node')
    expect(resolveThinkingMapNodeSlash('flow_map', 'delete', 'peer')).toBe('delete')
  })

  it('adds a similarity on the shared level and a difference from a side node', () => {
    expect(resolveThinkingMapNodeSlash('double_bubble_map', 'sibling', 'topic')).toBe('add_node')
    expect(resolveThinkingMapNodeSlash('double_bubble_map', 'sibling', 'peer')).toBe('add_node')
    expect(resolveThinkingMapNodeSlash('double_bubble_map', 'sibling', 'nested')).toBe('add_child')
    expect(resolveThinkingMapNodeSlash('double_bubble_map', 'delete', 'peer')).toBe('delete')
  })

  it('adds a brace branch on the current level and a subpart from a nested part', () => {
    expect(resolveThinkingMapNodeSlash('brace_map', 'sibling', 'topic')).toBe('add_branch')
    expect(resolveThinkingMapNodeSlash('brace_map', 'sibling', 'peer')).toBe('add_branch')
    expect(resolveThinkingMapNodeSlash('brace_map', 'sibling', 'nested')).toBe('add_child')
    expect(resolveThinkingMapNodeSlash('brace_map', 'delete', 'peer')).toBe('delete')
  })

  it('adds a cause on the first level and an effect from an effect node', () => {
    expect(resolveThinkingMapNodeSlash('multi_flow_map', 'sibling', 'topic')).toBe('add_node')
    expect(resolveThinkingMapNodeSlash('multi_flow_map', 'sibling', 'peer')).toBe('add_node')
    expect(resolveThinkingMapNodeSlash('multi_flow_map', 'sibling', 'nested')).toBe('add_child')
    expect(resolveThinkingMapNodeSlash('multi_flow_map', 'delete', 'peer')).toBe('delete')
  })

  it('leaves mind maps and concept maps on their own slash path', () => {
    expect(resolveThinkingMapNodeSlash('mindmap', 'sibling', 'peer')).toBeNull()
    expect(resolveThinkingMapNodeSlash('concept_map', 'delete', 'other')).toBeNull()
  })
})

describe('readThinkingMapSlashRole', () => {
  it('reads tree, flow, and brace depth', () => {
    const treeNodes = [
      node('tree-topic', 'topic'),
      node('cat', 'branch', { nodeType: 'branch' }),
      node('leaf', 'branch', { nodeType: 'leaf' }),
    ]
    expect(readThinkingMapSlashRole('tree_map', 'tree-topic', treeNodes, [])).toBe('topic')
    expect(readThinkingMapSlashRole('tree_map', 'cat', treeNodes, [])).toBe('peer')
    expect(readThinkingMapSlashRole('tree_map', 'leaf', treeNodes, [])).toBe('nested')

    const flowNodes = [
      node('flow-topic', 'topic'),
      node('step', 'flow'),
      node('sub', 'flowSubstep'),
    ]
    expect(readThinkingMapSlashRole('flow_map', 'flow-topic', flowNodes, [])).toBe('topic')
    expect(readThinkingMapSlashRole('flow_map', 'step', flowNodes, [])).toBe('peer')
    expect(readThinkingMapSlashRole('flow_map', 'sub', flowNodes, [])).toBe('nested')

    const braceNodes = [node('whole', 'topic'), node('part', 'brace'), node('subpart', 'brace')]
    const braceEdges: Connection[] = [
      { id: 'e1', source: 'whole', target: 'part' },
      { id: 'e2', source: 'part', target: 'subpart' },
    ]
    expect(readThinkingMapSlashRole('brace_map', 'whole', braceNodes, braceEdges)).toBe('topic')
    expect(readThinkingMapSlashRole('brace_map', 'part', braceNodes, braceEdges)).toBe('peer')
    expect(readThinkingMapSlashRole('brace_map', 'subpart', braceNodes, braceEdges)).toBe('nested')

    const bubbleNodes = [
      node('left-topic', 'topic'),
      node('sim', 'bubble', { doubleBubbleRole: 'similarity' }),
      node('diff', 'bubble', { doubleBubbleRole: 'leftDiff' }),
    ]
    expect(readThinkingMapSlashRole('double_bubble_map', 'left-topic', bubbleNodes, [])).toBe(
      'topic'
    )
    expect(readThinkingMapSlashRole('double_bubble_map', 'sim', bubbleNodes, [])).toBe('peer')
    expect(readThinkingMapSlashRole('double_bubble_map', 'diff', bubbleNodes, [])).toBe('nested')

    const multiFlowNodes = [
      node('event', 'topic'),
      node('cause', 'flow', { multiFlowRole: 'cause' }),
      node('effect', 'flow', { multiFlowRole: 'effect' }),
    ]
    expect(readThinkingMapSlashRole('multi_flow_map', 'event', multiFlowNodes, [])).toBe('topic')
    expect(readThinkingMapSlashRole('multi_flow_map', 'cause', multiFlowNodes, [])).toBe('peer')
    expect(readThinkingMapSlashRole('multi_flow_map', 'effect', multiFlowNodes, [])).toBe('nested')
  })
})
