/**
 * Maite learning map curriculum stubs (modules 8-13).
 */
export interface MaiteCurriculumNode {
  key: string
  name: string
}

export interface MaiteCurriculumModule {
  id: string
  title: string
  gradeBand: string
  knowledgeNodes: MaiteCurriculumNode[]
  thinkingNodes: MaiteCurriculumNode[]
}

export const MAITE_MAP_CURRICULUM: MaiteCurriculumModule[] = [
  {
    id: 'module-8',
    title: '有理数与代数式',
    gradeBand: '八年级',
    knowledgeNodes: [
      { key: 'rational-numbers', name: '有理数运算' },
      { key: 'algebraic-expressions', name: '代数式化简' },
      { key: 'linear-equations', name: '一元一次方程' },
    ],
    thinkingNodes: [
      { key: 'number-sense', name: '数感建模' },
      { key: 'symbol-reasoning', name: '符号推理' },
      { key: 'equation-strategy', name: '方程策略选择' },
    ],
  },
  {
    id: 'module-9',
    title: '函数与几何基础',
    gradeBand: '九年级',
    knowledgeNodes: [
      { key: 'linear-functions', name: '一次函数' },
      { key: 'quadratic-basics', name: '二次函数入门' },
      { key: 'triangle-properties', name: '三角形性质' },
    ],
    thinkingNodes: [
      { key: 'graph-reading', name: '图像读数' },
      { key: 'pattern-generalization', name: '规律概括' },
      { key: 'proof-sketch', name: '证明草图' },
    ],
  },
  {
    id: 'module-10',
    title: '方程与不等式',
    gradeBand: '十年级',
    knowledgeNodes: [
      { key: 'quadratic-equations', name: '一元二次方程' },
      { key: 'inequalities', name: '不等式组' },
      { key: 'systems', name: '方程组' },
    ],
    thinkingNodes: [
      { key: 'case-splitting', name: '分类讨论' },
      { key: 'constraint-modeling', name: '约束建模' },
      { key: 'solution-check', name: '解的检验' },
    ],
  },
  {
    id: 'module-11',
    title: '三角与向量',
    gradeBand: '十一年级',
    knowledgeNodes: [
      { key: 'trig-identities', name: '三角恒等变换' },
      { key: 'sine-cosine-law', name: '正余弦定理' },
      { key: 'vector-basics', name: '平面向量' },
    ],
    thinkingNodes: [
      { key: 'angle-relation', name: '角关系迁移' },
      { key: 'geometry-algebra-bridge', name: '数形结合' },
      { key: 'decomposition', name: '结构分解' },
    ],
  },
  {
    id: 'module-12',
    title: '概率与统计',
    gradeBand: '十二年级',
    knowledgeNodes: [
      { key: 'probability-rules', name: '概率计算' },
      { key: 'distribution-basics', name: '分布基础' },
      { key: 'statistics-inference', name: '统计推断' },
    ],
    thinkingNodes: [
      { key: 'sample-space', name: '样本空间建模' },
      { key: 'conditional-thinking', name: '条件思维' },
      { key: 'uncertainty-reasoning', name: '不确定性推理' },
    ],
  },
  {
    id: 'module-13',
    title: '综合与应用',
    gradeBand: '高三综合',
    knowledgeNodes: [
      { key: 'derivatives', name: '导数与应用' },
      { key: 'sequences', name: '数列综合' },
      { key: 'solid-geometry', name: '立体几何' },
    ],
    thinkingNodes: [
      { key: 'multi-step-planning', name: '多步规划' },
      { key: 'variant-transfer', name: '变式迁移' },
      { key: 'error-diagnosis', name: '错因诊断' },
    ],
  },
]

export function findCurriculumNode(
  nodeKey: string
): { module: MaiteCurriculumModule; node: MaiteCurriculumNode; graphType: 'knowledge' | 'thinking' } | null {
  for (const module of MAITE_MAP_CURRICULUM) {
    const knowledge = module.knowledgeNodes.find((node) => node.key === nodeKey)
    if (knowledge) {
      return { module, node: knowledge, graphType: 'knowledge' }
    }
    const thinking = module.thinkingNodes.find((node) => node.key === nodeKey)
    if (thinking) {
      return { module, node: thinking, graphType: 'thinking' }
    }
  }
  return null
}
