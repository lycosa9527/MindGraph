import { describe, expect, it } from 'vitest'

import { oneSentenceGuideRowsForDiagram } from '@/config/oneSentenceNodeActionGuide'
import { oneSentenceSuggestionKeysForDiagram } from '@/config/oneSentenceNodeActionSuggestions'
import type { Connection, DiagramNode } from '@/types'
import { collectMindMapExplainContext } from '@/utils/mindMapExplainContext'

function node(
  id: string,
  text: string,
  type: DiagramNode['type'],
  data?: Record<string, unknown>
): DiagramNode {
  return { id, text, type, data }
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
    expect(ctx?.nodeRole).toBe('branch')
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
    expect(ctx?.nodeRole).toBe('item')
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
    expect(ctx?.nodeRole).toBe('context')
  })

  it('includes causes that point at the multi-flow event', () => {
    const nodes = [
      node('event', '迟到', 'topic'),
      node('cause-0', '堵车', 'flow'),
      node('effect-0', '批评', 'flow'),
    ]
    const connections = [edge('cause-0', 'event'), edge('event', 'effect-0')]
    const ctx = collectMindMapExplainContext(nodes, connections, 'cause-0', 'multi_flow_map')
    expect(ctx?.topic).toBe('迟到')
    expect(ctx?.nodeRole).toBe('cause')
    expect(ctx?.topLevelBranches).toEqual(['堵车'])
    expect(ctx?.childBranches).toEqual(['批评'])
    expect(ctx?.siblingBranches).toEqual([])
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
    expect(ctx?.nodeRole).toBe('analogy')
  })

  it('joins both double-bubble centers', () => {
    const nodes = [
      node('left-topic', '猫', 'topic'),
      node('right-topic', '狗', 'topic'),
      node('similarity-0', '宠物', 'bubble'),
    ]
    const connections = [edge('left-topic', 'similarity-0'), edge('right-topic', 'similarity-0')]
    const ctx = collectMindMapExplainContext(
      nodes,
      connections,
      'similarity-0',
      'double_bubble_map'
    )
    expect(ctx?.topic).toBe('猫 / 狗')
    expect(ctx?.nodeRole).toBe('similarity')
    expect(ctx?.topLevelBranches).toEqual(['宠物'])
    expect(ctx?.childBranches).toEqual([])
  })
})

describe('diagram roles survive canvas link shape', () => {
  it('keeps tree leaves as peers even when the canvas chains them', () => {
    const nodes = [
      node('tree-topic', '动物', 'topic'),
      node('mammal', '哺乳', 'branch', { nodeType: 'branch', categoryIndex: 0 }),
      node('bird', '鸟类', 'branch', { nodeType: 'branch', categoryIndex: 1 }),
      node('cat', '猫', 'branch', {
        nodeType: 'leaf',
        leafIndex: 0,
        parentCategoryId: 'mammal',
        categoryIndex: 0,
      }),
      node('dog', '狗', 'branch', {
        nodeType: 'leaf',
        leafIndex: 1,
        parentCategoryId: 'mammal',
        categoryIndex: 0,
      }),
    ]
    const connections = [
      edge('tree-topic', 'mammal'),
      edge('tree-topic', 'bird'),
      edge('mammal', 'cat'),
      edge('cat', 'dog'),
    ]
    const leaf = collectMindMapExplainContext(nodes, connections, 'dog', 'tree_map')
    expect(leaf?.nodeRole).toBe('item')
    expect(leaf?.ancestorPath).toEqual(['哺乳'])
    expect(leaf?.siblingBranches).toEqual(['猫'])
    expect(leaf?.childBranches).toEqual([])
    expect(leaf?.topLevelBranches).toEqual(['哺乳', '鸟类'])
    const category = collectMindMapExplainContext(nodes, connections, 'mammal', 'tree_map')
    expect(category?.nodeRole).toBe('category')
    expect(category?.childBranches).toEqual(['猫', '狗'])
    expect(category?.siblingBranches).toEqual(['鸟类'])
  })

  it('keeps flow steps in order and substeps under their step', () => {
    const nodes = [
      node('flow-topic', '番茄炒鸡蛋', 'topic'),
      node('wash', '打蛋', 'flow', { stepIndex: 0 }),
      node('cook', '翻炒', 'flow', { stepIndex: 1 }),
      node('salt', '加盐', 'flowSubstep', { parentStepId: 'cook', substepIndex: 0, stepIndex: 1 }),
    ]
    const connections = [edge('flow-topic', 'wash'), edge('wash', 'cook'), edge('cook', 'salt')]
    const step = collectMindMapExplainContext(nodes, connections, 'cook', 'flow_map')
    expect(step?.nodeRole).toBe('step')
    expect(step?.topLevelBranches).toEqual(['打蛋', '翻炒'])
    expect(step?.siblingBranches).toEqual(['打蛋'])
    expect(step?.childBranches).toEqual(['加盐'])
    expect(step?.ancestorPath).toEqual([])
    const sub = collectMindMapExplainContext(nodes, connections, 'salt', 'flow_map')
    expect(sub?.nodeRole).toBe('substep')
    expect(sub?.ancestorPath).toEqual(['翻炒'])
    expect(sub?.siblingBranches).toEqual([])
    expect(sub?.childBranches).toEqual([])
  })

  it('keeps brace parts and subparts on the real parent', () => {
    const nodes = [
      node('brace-whole', '自行车', 'whole'),
      node('wheel', '车轮', 'brace'),
      node('spoke', '辐条', 'brace'),
    ]
    const connections = [edge('brace-whole', 'wheel'), edge('wheel', 'spoke')]
    const part = collectMindMapExplainContext(nodes, connections, 'wheel', 'brace_map')
    expect(part?.nodeRole).toBe('part')
    expect(part?.childBranches).toEqual(['辐条'])
    expect(part?.siblingBranches).toEqual([])
    const sub = collectMindMapExplainContext(nodes, connections, 'spoke', 'brace_map')
    expect(sub?.nodeRole).toBe('subpart')
    expect(sub?.ancestorPath).toEqual(['车轮'])
    const whole = collectMindMapExplainContext(nodes, connections, 'brace-whole', 'brace_map')
    expect(whole?.nodeRole).toBe('whole')
    expect(whole?.topLevelBranches).toEqual(['车轮'])
    expect(whole?.childBranches).toEqual([])
  })

  it('puts the other side of a double-bubble difference on its own list', () => {
    const nodes = [
      node('left-topic', '猫', 'topic'),
      node('right-topic', '狗', 'topic'),
      node('similarity-0', '宠物', 'bubble'),
      node('left-diff-0', '会爬树', 'bubble'),
      node('right-diff-0', '会游泳', 'bubble'),
    ]
    const ctx = collectMindMapExplainContext(nodes, [], 'left-diff-0', 'double_bubble_map')
    expect(ctx?.nodeRole).toBe('left_diff')
    expect(ctx?.topLevelBranches).toEqual(['宠物'])
    expect(ctx?.siblingBranches).toEqual([])
    expect(ctx?.childBranches).toEqual(['右：会游泳'])
  })

  it('names the concept-map relationship instead of a branch', () => {
    const nodes = [
      node('topic', '植物', 'topic'),
      node('leaf', '叶子', 'branch'),
      node('root', '根', 'branch'),
    ]
    const connections = [
      { ...edge('topic', 'leaf'), label: '具有' },
      { ...edge('topic', 'root'), label: '长出' },
    ]
    const ctx = collectMindMapExplainContext(nodes, connections, 'leaf', 'concept_map')
    expect(ctx?.nodeRole).toBe('concept')
    expect(ctx?.topic).toBe('植物')
    expect(ctx?.topLevelBranches).toEqual(['根'])
    expect(ctx?.siblingBranches).toEqual(['植物 —具有→'])
  })

  it('pairs bridge sides by pairIndex', () => {
    const nodes = [
      node('dimension-label', '像', 'label'),
      node('eye', '眼睛', 'branch', { pairIndex: 0, position: 'left' }),
      node('camera', '相机', 'branch', { pairIndex: 0, position: 'right' }),
      node('ear', '耳朵', 'branch', { pairIndex: 1, position: 'left' }),
      node('mic', '麦克风', 'branch', { pairIndex: 1, position: 'right' }),
    ]
    const ctx = collectMindMapExplainContext(nodes, [], 'eye', 'bridge_map')
    expect(ctx?.nodeRole).toBe('analogy_left')
    expect(ctx?.topic).toBe('像')
    expect(ctx?.topLevelBranches).toEqual(['眼睛 / 相机', '耳朵 / 麦克风'])
    expect(ctx?.siblingBranches).toEqual(['相机'])
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
