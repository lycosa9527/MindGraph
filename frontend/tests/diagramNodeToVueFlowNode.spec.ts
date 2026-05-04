import { describe, expect, it } from 'vitest'

import { diagramNodeToVueFlowNode } from '@/types/vueflow'
import type { DiagramNode } from '@/types/diagram'

// ---------------------------------------------------------------------------
// Minimal helpers
// ---------------------------------------------------------------------------

function makeNode(overrides: Partial<DiagramNode> = {}): DiagramNode {
  return {
    id: 'node-1',
    type: 'topic',
    text: 'Hello',
    position: { x: 0, y: 0 },
    ...overrides,
  } as DiagramNode
}

// ---------------------------------------------------------------------------
// label precedence — Fix 1
// ---------------------------------------------------------------------------

describe('diagramNodeToVueFlowNode — label precedence', () => {
  it('uses node.text as data.label when data is absent', () => {
    const node = makeNode({ text: 'My Topic', data: undefined })
    const vf = diagramNodeToVueFlowNode(node, 'mind_map')
    expect(vf.data.label).toBe('My Topic')
  })

  it('node.text wins over a stale data.label', () => {
    // This is the core collab sync bug: guest edits set node.text but leave
    // data.label unchanged.  After Fix 1, node.text must always win.
    const node = makeNode({
      text: 'Updated by guest',
      data: { label: 'Stale old label', someCustomField: 42 },
    })
    const vf = diagramNodeToVueFlowNode(node, 'mind_map')
    expect(vf.data.label).toBe('Updated by guest')
  })

  it('preserves other custom fields from data when label is overridden', () => {
    const node = makeNode({
      text: 'New Text',
      data: { label: 'Old Label', pairIndex: 3, position: 'top' },
    })
    const vf = diagramNodeToVueFlowNode(node, 'bridge_map')
    expect(vf.data.label).toBe('New Text')
    expect((vf.data as Record<string, unknown>).pairIndex).toBe(3)
    expect((vf.data as Record<string, unknown>).position).toBe('top')
  })

  it('node.text wins even when data.label is an empty string', () => {
    const node = makeNode({
      text: 'Real text',
      data: { label: '' },
    })
    const vf = diagramNodeToVueFlowNode(node, 'bubble_map')
    expect(vf.data.label).toBe('Real text')
  })

  it('handles undefined node.text gracefully', () => {
    const node = makeNode({ text: undefined as unknown as string, data: { label: 'from data' } })
    const vf = diagramNodeToVueFlowNode(node, 'mind_map')
    // node.text is undefined — label should be undefined (not data.label overriding it)
    expect(vf.data.label).toBeUndefined()
  })
})

// ---------------------------------------------------------------------------
// originalNode is always the input node
// ---------------------------------------------------------------------------

describe('diagramNodeToVueFlowNode — originalNode', () => {
  it('attaches the original node object in data.originalNode', () => {
    const node = makeNode({ text: 'Test' })
    const vf = diagramNodeToVueFlowNode(node, 'mind_map')
    expect(vf.data.originalNode).toBe(node)
  })
})
