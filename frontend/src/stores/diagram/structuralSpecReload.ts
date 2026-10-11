import type { DiagramNode } from '@/types'

const STRUCTURAL_SESSION_KEYS = [
  '_node_styles',
  '_customPositions',
  '_mindmap_theme',
  '_mindmap_adornments',
  'isLearningSheet',
  'is_learning_sheet',
  'learningSheetShowAnswers',
  'learning_sheet_show_answers',
  'hiddenAnswers',
  'learningSheetBaseline',
  'learning_sheet_baseline',
] as const

export function structuralSessionCarry(
  data: Record<string, unknown> | undefined
): Record<string, unknown> | undefined {
  if (!data) return undefined
  const carried: Record<string, unknown> = {}
  for (const key of STRUCTURAL_SESSION_KEYS) {
    if (data[key] !== undefined) carried[key] = data[key]
  }
  return Object.keys(carried).length > 0 ? carried : undefined
}

function hiddenAnswerFields(node: DiagramNode | undefined): Record<string, unknown> | undefined {
  const data = node?.data
  if (!data) return undefined
  const answer = typeof data.hiddenAnswer === 'string' ? data.hiddenAnswer : ''
  const secondary = typeof data.hiddenAnswerSecondary === 'string' ? data.hiddenAnswerSecondary : ''
  if (!answer && !secondary) return undefined
  return {
    ...(answer ? { hiddenAnswer: answer } : {}),
    ...(secondary ? { hiddenAnswerSecondary: secondary } : {}),
  }
}

/** Keep typography and worksheet answers on nodes whose ids survive a structure reload. */
export function mergeReloadedNodeFields(
  nodes: DiagramNode[],
  previous: DiagramNode[] | undefined,
  structural: boolean
): DiagramNode[] {
  if (!previous || previous.length === 0) return nodes
  const prevById = new Map(previous.map((node) => [node.id, node] as const))
  return nodes.map((node) => {
    const prev = prevById.get(node.id)
    if (!prev) return node
    const answers = structural ? hiddenAnswerFields(prev) : undefined
    if (!prev.style && !answers) return node
    return {
      ...node,
      ...(prev.style ? { style: { ...prev.style, ...node.style } } : {}),
      ...(answers ? { data: { ...(node.data ?? {}), ...answers } } : {}),
    }
  })
}
