import { describe, expect, it } from 'vitest'

import { oneSentenceGuideRowsForDiagram } from '@/config/oneSentenceNodeActionGuide'
import { oneSentenceSuggestionKeysForDiagram } from '@/config/oneSentenceNodeActionSuggestions'
import type { Connection, DiagramNode } from '@/types'
import { collectMindMapExplainContext } from '@/utils/mindMapExplainContext'

function node(id: string, text: string, type: DiagramNode['type']): DiagramNode {
  return { id, text, type }
}

function edge(source: string, target: string): Connection {
  return { id: `${source}-${target}`, source, target }
}

describe('collectMindMapExplainContext', () => {
  it('keeps a mind-map branch under its topic and siblings', () => {
    const nodes = [
      node('topic', '中国', 'topic'),
      node('b1', '历史', 'branch'),
      node('b2', '地理', 'branch'),
      node('c1', '唐朝', 'branch'),
    ]
    const connections = [edge('topic', 'b1'), edge('topic', 'b2'), edge('b1', 'c1')]
    const ctx = collectMindMapExplainContext(nodes, connections, 'b1', 'mindmap')
    expect(ctx?.topic).toBe('中国')
    expect(ctx?.topLevelBranches).toEqual(['历史', '地理'])
    expect(ctx?.siblingBranches).toEqual(['地理'])
    expect(ctx?.childBranches).toEqual(['唐朝'])
    expect(ctx?.ancestorPath).toEqual([])
  })

  it('uses the tree topic and the category above a leaf', () => {
    const nodes = [
      node('tree-topic', '动物', 'topic'),
      node('cat', '哺乳', 'branch'),
      node('leaf', '猫', 'branch'),
    ]
    const connections = [edge('tree-topic', 'cat'), edge('cat', 'leaf')]
    const ctx = collectMindMapExplainContext(nodes, connections, 'leaf', 'tree_map')
    expect(ctx?.diagramType).toBe('tree_map')
    expect(ctx?.topic).toBe('动物')
    expect(ctx?.ancestorPath).toEqual(['哺乳'])
    expect(ctx?.siblingBranches).toEqual([])
    expect(ctx?.topLevelBranches).toEqual(['哺乳'])
  })

  it('treats circle contexts as siblings when the map has no edges', () => {
    const nodes = [
      node('outer-boundary', '', 'boundary'),
      node('topic', '水果', 'center'),
      node('c1', '苹果', 'bubble'),
      node('c2', '香蕉', 'bubble'),
    ]
    const ctx = collectMindMapExplainContext(nodes, [], 'c1', 'circle_map')
    expect(ctx?.topic).toBe('水果')
    expect(ctx?.topLevelBranches).toEqual(['苹果', '香蕉'])
    expect(ctx?.siblingBranches).toEqual(['香蕉'])
    expect(ctx?.childBranches).toEqual([])
  })

  it('includes causes that point at the multi-flow event', () => {
    const nodes = [
      node('event', '迟到', 'topic'),
      node('cause', '堵车', 'flow'),
      node('effect', '批评', 'flow'),
    ]
    const connections = [edge('cause', 'event'), edge('event', 'effect')]
    const ctx = collectMindMapExplainContext(nodes, connections, 'cause', 'multi_flow_map')
    expect(ctx?.topic).toBe('迟到')
    expect(ctx?.topLevelBranches).toEqual(['批评', '堵车'])
    expect(ctx?.siblingBranches).toEqual(['批评'])
  })

  it('uses the bridge dimension and the other pair node', () => {
    const nodes = [
      node('dimension-label', '像', 'label'),
      node('left', '眼睛', 'branch'),
      node('right', '相机', 'branch'),
    ]
    const ctx = collectMindMapExplainContext(nodes, [], 'left', 'bridge_map')
    expect(ctx?.topic).toBe('像')
    expect(ctx?.siblingBranches).toEqual(['相机'])
  })

  it('joins both double-bubble centers', () => {
    const nodes = [
      node('left-topic', '猫', 'topic'),
      node('right-topic', '狗', 'topic'),
      node('sim', '宠物', 'bubble'),
    ]
    const connections = [edge('left-topic', 'sim'), edge('right-topic', 'sim')]
    const ctx = collectMindMapExplainContext(nodes, connections, 'sim', 'double_bubble_map')
    expect(ctx?.topic).toBe('猫 / 狗')
    expect(ctx?.topLevelBranches).toEqual(['宠物'])
  })
})

describe('one sentence prompts by diagram', () => {
  it('drops mind-map-only prompts on a thinking map', () => {
    const rows = oneSentenceGuideRowsForDiagram('circle_map').map((row) => row.id)
    expect(rows).not.toContain('auto_complete_branch')
    expect(rows).not.toContain('set_branch_numbering')
    expect(rows).toContain('explain_node')
    const keys = oneSentenceSuggestionKeysForDiagram('flow_map')
    expect(keys.some((key) => key.includes('set_branch_numbering'))).toBe(false)
    expect(oneSentenceGuideRowsForDiagram('mindmap').map((row) => row.id)).toContain(
      'set_branch_numbering'
    )
  })
})
