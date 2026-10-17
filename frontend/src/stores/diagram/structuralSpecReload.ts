import type { DiagramNode } from '@/types'

import { LEARNING_SHEET_BLANK_TEXT, isLearningSheetBlankDisplayText } from '../specLoader/utils'

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

function wasBlanked(node: DiagramNode): boolean {
  const data = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
  const answer = typeof data?.hiddenAnswer === 'string' ? data.hiddenAnswer.trim() : ''
  if (!answer) return false
  return data?.hidden === true || isLearningSheetBlankDisplayText(node.text)
}

function carriedHold(node: DiagramNode): Record<string, number> {
  const data = node.data as
    { learningSheetHoldWidth?: unknown; learningSheetHoldHeight?: unknown } | undefined
  const hold: Record<string, number> = {}
  if (typeof data?.learningSheetHoldWidth === 'number' && data.learningSheetHoldWidth > 0) {
    hold.learningSheetHoldWidth = data.learningSheetHoldWidth
  }
  if (typeof data?.learningSheetHoldHeight === 'number' && data.learningSheetHoldHeight > 0) {
    hold.learningSheetHoldHeight = data.learningSheetHoldHeight
  }
  return hold
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
    if (structural && wasBlanked(prev)) {
      return {
        ...node,
        text: LEARNING_SHEET_BLANK_TEXT,
        textSecondary: '',
        ...(prev.style ? { style: { ...prev.style, ...node.style } } : {}),
        data: {
          ...(node.data ?? {}),
          ...(answers ?? {}),
          ...carriedHold(prev),
          hidden: true,
          label: LEARNING_SHEET_BLANK_TEXT,
          labelSecondary: '',
        },
      }
    }
    if (!prev.style && !answers) return node
    return {
      ...node,
      ...(prev.style ? { style: { ...prev.style, ...node.style } } : {}),
      ...(answers ? { data: { ...(node.data ?? {}), ...answers } } : {}),
    }
  })
}
