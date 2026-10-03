import { describe, expect, it } from 'vitest'

import { attachRemainingSecondary } from '@/diagramBilingual/attachRest'
import { offsetFlowLayoutForSecondary } from '@/diagramBilingual/flowLayout'
import { secondaryLineBoxHeight, stackedTextBlock } from '@/diagramBilingual/measure'
import type { DiagramNode } from '@/types'

describe('stackedTextBlock', () => {
  it('returns the primary box when the second line is empty', () => {
    expect(stackedTextBlock(80, 40, 120, 16, '  ')).toEqual({ width: 80, height: 40 })
  })

  it('uses the wider line and adds the secondary line box', () => {
    const box = stackedTextBlock(80, 40, 120, 16, 'photosynthesis')
    expect(box.width).toBe(120)
    expect(box.height).toBe(40 + Math.ceil(16 * 0.75 * 1.2))
  })
})

describe('attachRemainingSecondary', () => {
  it('stamps flow steps from the sibling mirror without touching a gloss that is already set', () => {
    const nodes: DiagramNode[] = [
      { id: 'flow-topic', text: '做蛋糕', type: 'topic', position: { x: 0, y: 0 } },
      { id: 'step-0', text: '搅拌', type: 'flow', position: { x: 0, y: 0 }, textSecondary: '已有' },
      { id: 'step-1', text: '烘烤', type: 'flow', position: { x: 0, y: 0 } },
    ]
    attachRemainingSecondary('flow_map', nodes, {
      title: '做蛋糕',
      steps: ['搅拌', '烘烤'],
      secondary: { title: 'Bake a cake', steps: ['Mix', 'Bake'] },
    })
    expect(nodes[0].textSecondary).toBe('Bake a cake')
    expect(nodes[1].textSecondary).toBe('已有')
    expect(nodes[2].textSecondary).toBe('Bake')
  })

  it('does not move a later flow gloss onto a step whose second line is shorter', () => {
    const nodes: DiagramNode[] = [
      {
        id: 's0',
        text: '一',
        type: 'flow',
        position: { x: 0, y: 0 },
        data: { stepIndex: 0 },
      },
      {
        id: 's1',
        text: '二',
        type: 'flow',
        position: { x: 0, y: 0 },
        data: { stepIndex: 1 },
      },
      {
        id: 'a',
        text: '甲',
        type: 'flowSubstep',
        position: { x: 0, y: 0 },
        data: { stepIndex: 0, parentStepId: 's0' },
      },
      {
        id: 'b',
        text: '乙',
        type: 'flowSubstep',
        position: { x: 0, y: 0 },
        data: { stepIndex: 0, parentStepId: 's0' },
      },
      {
        id: 'c',
        text: '丙',
        type: 'flowSubstep',
        position: { x: 0, y: 0 },
        data: { stepIndex: 1, parentStepId: 's1' },
      },
    ]
    attachRemainingSecondary('flow_map', nodes, {
      title: '流程',
      steps: ['一', '二'],
      substeps: [
        { step: '一', substeps: ['甲', '乙'] },
        { step: '二', substeps: ['丙'] },
      ],
      secondary: {
        steps: ['One', 'Two'],
        substeps: [{ substeps: ['A'] }, { substeps: ['C'] }],
      },
    })
    expect(nodes[2].textSecondary).toBe('A')
    expect(nodes[3].textSecondary).toBeUndefined()
    expect(nodes[4].textSecondary).toBe('C')
  })

  it('keeps an empty tree gloss from shifting the next line', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: '动物', type: 'topic', position: { x: 0, y: 0 } },
      { id: 'cat', text: '哺乳', type: 'branch', position: { x: 0, y: 0 } },
      { id: 'leaf-a', text: '狗', type: 'branch', position: { x: 0, y: 0 } },
      { id: 'leaf-b', text: '猫', type: 'branch', position: { x: 0, y: 0 } },
    ]
    attachRemainingSecondary('tree_map', nodes, {
      topic: '动物',
      children: [
        {
          text: '哺乳',
          children: [
            { text: '狗', children: [] },
            { text: '猫', children: [] },
          ],
        },
      ],
      secondary: {
        topic: 'Animals',
        children: [
          {
            text: 'Mammals',
            children: [
              { text: '', children: [] },
              { text: 'Cat', children: [] },
            ],
          },
        ],
      },
    })
    expect(nodes[0].textSecondary).toBe('Animals')
    expect(nodes[1].textSecondary).toBe('Mammals')
    expect(nodes[2].textSecondary).toBeUndefined()
    expect(nodes[3].textSecondary).toBe('Cat')
  })

  it('stamps concept-map topic and concepts from the sibling mirror', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: '光合作用', type: 'topic', position: { x: 0, y: 0 } },
      { id: 'concept-0', text: '叶绿体', type: 'branch', position: { x: 0, y: 0 } },
      { id: 'concept-1', text: '阳光', type: 'branch', position: { x: 0, y: 0 } },
    ]
    attachRemainingSecondary('concept_map', nodes, {
      topic: '光合作用',
      concepts: ['叶绿体', '阳光'],
      secondary: { topic: 'Photosynthesis', concepts: ['Chloroplast', 'Sunlight'] },
    })
    expect(nodes[0].textSecondary).toBe('Photosynthesis')
    expect(nodes[1].textSecondary).toBe('Chloroplast')
    expect(nodes[2].textSecondary).toBe('Sunlight')
  })
})

describe('offsetFlowLayoutForSecondary', () => {
  it('moves substeps down by the step gloss and leaves a mono flow in place', () => {
    const nodes: DiagramNode[] = [
      {
        id: 'flow-topic',
        text: '做蛋糕',
        type: 'topic',
        position: { x: 0, y: 0 },
        data: { orientation: 'horizontal' },
      },
      {
        id: 'step-0',
        text: '搅拌',
        textSecondary: 'Mix',
        type: 'flow',
        position: { x: 80, y: 40 },
        data: { stepIndex: 0 },
      },
      {
        id: 'sub-0',
        text: '面粉',
        type: 'flowSubstep',
        position: { x: 80, y: 100 },
        data: { parentStepId: 'step-0', substepIndex: 0 },
      },
    ]
    const shifted = offsetFlowLayoutForSecondary(nodes)
    expect(shifted[0]).toBe(nodes[0])
    expect(shifted[1]).toBe(nodes[1])
    expect(shifted[2].position?.y).toBe(100 + secondaryLineBoxHeight(16))
    const mono: DiagramNode[] = [
      { id: 'flow-topic', text: 'Cake', type: 'topic', position: { x: 0, y: 0 } },
      { id: 'step-0', text: 'Mix', type: 'flow', position: { x: 1, y: 2 }, data: { stepIndex: 0 } },
    ]
    expect(offsetFlowLayoutForSecondary(mono)).toBe(mono)
  })
})
