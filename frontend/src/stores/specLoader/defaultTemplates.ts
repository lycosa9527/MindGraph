/**
 * Default diagram specs for new / blank canvas — locale-aware (zh vs en/az).
 */
import type { LocaleCode } from '@/i18n/locales'
import {
  defaultUiLocaleGroup,
  getConceptMapFocusQuestionDefault,
  getConceptMapRootConceptText,
  getConceptMapTopicRootRelationshipLabel,
} from '@/stores/diagram/diagramDefaultLabels'
import type { DiagramType } from '@/types'

function templatesForLocale(group: 'zh' | 'en'): Record<string, Record<string, unknown>> {
  const lang: LocaleCode = group === 'zh' ? 'zh' : 'en'
  const fq = getConceptMapFocusQuestionDefault(lang)
  const root = getConceptMapRootConceptText(lang)
  const rootEdge = getConceptMapTopicRootRelationshipLabel(lang)

  if (group === 'zh') {
    return {
      circle_map: {
        topic: '主题',
        context: ['联想1', '联想2', '联想3', '联想4', '联想5', '联想6', '联想7', '联想8'],
      },
      bubble_map: {
        topic: '主题',
        attributes: ['属性1', '属性2', '属性3', '属性4', '属性5'],
      },
      double_bubble_map: {
        left: '主题A',
        right: '主题B',
        similarities: ['相似点1', '相似点2'],
        left_differences: ['不同点A1', '不同点A2', '不同点A3'],
        right_differences: ['不同点B1', '不同点B2', '不同点B3'],
      },
      tree_map: {
        topic: '根主题',
        dimension: '',
        alternative_dimensions: [],
        children: [
          {
            text: '类别1',
            children: [
              { text: '项目1.1', children: [] },
              { text: '项目1.2', children: [] },
              { text: '项目1.3', children: [] },
            ],
          },
          {
            text: '类别2',
            children: [
              { text: '项目2.1', children: [] },
              { text: '项目2.2', children: [] },
              { text: '项目2.3', children: [] },
            ],
          },
          {
            text: '类别3',
            children: [
              { text: '项目3.1', children: [] },
              { text: '项目3.2', children: [] },
              { text: '项目3.3', children: [] },
            ],
          },
          {
            text: '类别4',
            children: [
              { text: '项目4.1', children: [] },
              { text: '项目4.2', children: [] },
              { text: '项目4.3', children: [] },
            ],
          },
        ],
      },
      brace_map: {
        whole: '主题',
        dimension: '',
        parts: [
          { name: '部分1', subparts: [{ name: '子部分1.1' }, { name: '子部分1.2' }] },
          { name: '部分2', subparts: [{ name: '子部分2.1' }, { name: '子部分2.2' }] },
          { name: '部分3', subparts: [{ name: '子部分3.1' }, { name: '子部分3.2' }] },
        ],
      },
      flow_map: {
        title: '事件流程',
        steps: ['步骤1', '步骤2', '步骤3', '步骤4'],
        substeps: [
          { step: '步骤1', substeps: ['子步骤1.1', '子步骤1.2'] },
          { step: '步骤2', substeps: ['子步骤2.1', '子步骤2.2'] },
          { step: '步骤3', substeps: ['子步骤3.1', '子步骤3.2'] },
          { step: '步骤4', substeps: ['子步骤4.1', '子步骤4.2'] },
        ],
      },
      multi_flow_map: {
        event: '事件',
        causes: ['原因1', '原因2', '原因3', '原因4'],
        effects: ['结果1', '结果2', '结果3', '结果4'],
      },
      bridge_map: {
        relating_factor: '[点击设置]',
        dimension: '',
        analogies: [
          { left: '事物A1', right: '事物B1' },
          { left: '事物A2', right: '事物B2' },
          { left: '事物A3', right: '事物B3' },
          { left: '事物A4', right: '事物B4' },
          { left: '事物A5', right: '事物B5' },
        ],
        alternative_dimensions: [],
      },
      mindmap: {
        topic: '中心主题',
        children: [
          {
            id: 'branch_0',
            label: '分支1',
            text: '分支1',
            children: [
              { id: 'sub_0_0', label: '子项1.1', text: '子项1.1', children: [] },
              { id: 'sub_0_1', label: '子项1.2', text: '子项1.2', children: [] },
            ],
          },
          {
            id: 'branch_1',
            label: '分支2',
            text: '分支2',
            children: [
              { id: 'sub_1_0', label: '子项2.1', text: '子项2.1', children: [] },
              { id: 'sub_1_1', label: '子项2.2', text: '子项2.2', children: [] },
            ],
          },
          {
            id: 'branch_2',
            label: '分支3',
            text: '分支3',
            children: [
              { id: 'sub_2_0', label: '子项3.1', text: '子项3.1', children: [] },
              { id: 'sub_2_1', label: '子项3.2', text: '子项3.2', children: [] },
            ],
          },
          {
            id: 'branch_3',
            label: '分支4',
            text: '分支4',
            children: [
              { id: 'sub_3_0', label: '子项4.1', text: '子项4.1', children: [] },
              { id: 'sub_3_1', label: '子项4.2', text: '子项4.2', children: [] },
            ],
          },
        ],
      },
      concept_map: {
        topic: fq,
        concepts: [root],
        relationships: [
          {
            from: fq,
            to: root,
            label: rootEdge,
          },
        ],
        focus_question: fq,
      },
    }
  }

  return {
    circle_map: {
      topic: 'Topic',
      context: [
        'Context 1',
        'Context 2',
        'Context 3',
        'Context 4',
        'Context 5',
        'Context 6',
        'Context 7',
        'Context 8',
      ],
    },
    bubble_map: {
      topic: 'Topic',
      attributes: ['Attribute 1', 'Attribute 2', 'Attribute 3', 'Attribute 4', 'Attribute 5'],
    },
    double_bubble_map: {
      left: 'Topic A',
      right: 'Topic B',
      similarities: ['Similarity 1', 'Similarity 2'],
      left_differences: ['Difference A1', 'Difference A2', 'Difference A3'],
      right_differences: ['Difference B1', 'Difference B2', 'Difference B3'],
    },
    tree_map: {
      topic: 'Root Topic',
      dimension: '',
      alternative_dimensions: [],
      children: [
        {
          text: 'Category 1',
          children: [
            { text: 'Item 1.1', children: [] },
            { text: 'Item 1.2', children: [] },
            { text: 'Item 1.3', children: [] },
          ],
        },
        {
          text: 'Category 2',
          children: [
            { text: 'Item 2.1', children: [] },
            { text: 'Item 2.2', children: [] },
            { text: 'Item 2.3', children: [] },
          ],
        },
        {
          text: 'Category 3',
          children: [
            { text: 'Item 3.1', children: [] },
            { text: 'Item 3.2', children: [] },
            { text: 'Item 3.3', children: [] },
          ],
        },
        {
          text: 'Category 4',
          children: [
            { text: 'Item 4.1', children: [] },
            { text: 'Item 4.2', children: [] },
            { text: 'Item 4.3', children: [] },
          ],
        },
      ],
    },
    brace_map: {
      whole: 'Topic',
      dimension: '',
      parts: [
        { name: 'Part 1', subparts: [{ name: 'Subpart 1.1' }, { name: 'Subpart 1.2' }] },
        { name: 'Part 2', subparts: [{ name: 'Subpart 2.1' }, { name: 'Subpart 2.2' }] },
        { name: 'Part 3', subparts: [{ name: 'Subpart 3.1' }, { name: 'Subpart 3.2' }] },
      ],
    },
    flow_map: {
      title: 'Process',
      steps: ['Step 1', 'Step 2', 'Step 3', 'Step 4'],
      substeps: [
        { step: 'Step 1', substeps: ['Substep 1.1', 'Substep 1.2'] },
        { step: 'Step 2', substeps: ['Substep 2.1', 'Substep 2.2'] },
        { step: 'Step 3', substeps: ['Substep 3.1', 'Substep 3.2'] },
        { step: 'Step 4', substeps: ['Substep 4.1', 'Substep 4.2'] },
      ],
    },
    multi_flow_map: {
      event: 'Main Event',
      causes: ['Cause 1', 'Cause 2', 'Cause 3', 'Cause 4'],
      effects: ['Effect 1', 'Effect 2', 'Effect 3', 'Effect 4'],
    },
    bridge_map: {
      relating_factor: '[Click to set]',
      dimension: '',
      analogies: [
        { left: 'Item A1', right: 'Item B1' },
        { left: 'Item A2', right: 'Item B2' },
        { left: 'Item A3', right: 'Item B3' },
        { left: 'Item A4', right: 'Item B4' },
        { left: 'Item A5', right: 'Item B5' },
      ],
      alternative_dimensions: [],
    },
    mindmap: {
      topic: 'Central Topic',
      children: [
        {
          id: 'branch_0',
          label: 'Branch 1',
          text: 'Branch 1',
          children: [
            { id: 'sub_0_0', label: 'Child 1.1', text: 'Child 1.1', children: [] },
            { id: 'sub_0_1', label: 'Child 1.2', text: 'Child 1.2', children: [] },
          ],
        },
        {
          id: 'branch_1',
          label: 'Branch 2',
          text: 'Branch 2',
          children: [
            { id: 'sub_1_0', label: 'Child 2.1', text: 'Child 2.1', children: [] },
            { id: 'sub_1_1', label: 'Child 2.2', text: 'Child 2.2', children: [] },
          ],
        },
        {
          id: 'branch_2',
          label: 'Branch 3',
          text: 'Branch 3',
          children: [
            { id: 'sub_2_0', label: 'Child 3.1', text: 'Child 3.1', children: [] },
            { id: 'sub_2_1', label: 'Child 3.2', text: 'Child 3.2', children: [] },
          ],
        },
        {
          id: 'branch_3',
          label: 'Branch 4',
          text: 'Branch 4',
          children: [
            { id: 'sub_3_0', label: 'Child 4.1', text: 'Child 4.1', children: [] },
            { id: 'sub_3_1', label: 'Child 4.2', text: 'Child 4.2', children: [] },
          ],
        },
      ],
    },
    concept_map: {
      topic: fq,
      concepts: [root],
      relationships: [
        {
          from: fq,
          to: root,
          label: rootEdge,
        },
      ],
      focus_question: fq,
    },
  }
}

const CACHE: Record<'zh' | 'en', Record<string, Record<string, unknown>>> = {
  zh: templatesForLocale('zh'),
  en: templatesForLocale('en'),
}

export function getDefaultTemplate(
  diagramType: DiagramType,
  language: LocaleCode
): Record<string, unknown> | null {
  const normalized: DiagramType = diagramType === 'mind_map' ? 'mindmap' : diagramType
  const group = defaultUiLocaleGroup(language)
  const table = CACHE[group]
  const spec = table[normalized]
  return spec ? { ...spec } : null
}
