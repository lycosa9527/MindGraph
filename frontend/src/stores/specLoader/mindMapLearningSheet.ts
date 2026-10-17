/**
 * Carry learning-sheet blanks across mind-map spec rebuilds (add/delete).
 */
import type { DiagramNode } from '@/types'

import type { MindMapBranchSpec } from './mindMapLegacyLayout'
import { LEARNING_SHEET_BLANK_TEXT, isLearningSheetBlankDisplayText } from './utils'

/** Fields layout and blank detection read. Spec collectors can pass this without a full node. */
export type LearningSheetTextSource = {
  text?: string
  textSecondary?: string
  data?: object
}

function nodeData(node: LearningSheetTextSource): {
  hidden?: boolean
  hiddenAnswer?: string
  hiddenAnswerSecondary?: string
} {
  return (node.data ?? {}) as {
    hidden?: boolean
    hiddenAnswer?: string
    hiddenAnswerSecondary?: string
  }
}

function nodeHiddenAnswer(node: LearningSheetTextSource): string | undefined {
  const raw = nodeData(node).hiddenAnswer
  if (typeof raw !== 'string') return undefined
  const trimmed = raw.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

export function isLearningSheetBlankedNode(node: LearningSheetTextSource | undefined): boolean {
  if (!node) return false
  const answer = nodeHiddenAnswer(node)
  if (!answer) return false
  return nodeData(node).hidden === true || isLearningSheetBlankDisplayText(node.text)
}

/** Layout / numbering estimates use the answer while the node is blanked. */
export function learningSheetLayoutText(node: LearningSheetTextSource): string {
  return isLearningSheetBlankedNode(node) ? (nodeHiddenAnswer(node) ?? '') : String(node.text ?? '')
}

/** Spec `text` is the answer so layout keeps underline width. */
function nodeHiddenAnswerSecondary(node: LearningSheetTextSource): string | undefined {
  const raw = nodeData(node).hiddenAnswerSecondary
  if (typeof raw !== 'string') return undefined
  const trimmed = raw.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

/** Gloss line used for layout. A blank keeps the stored answer gloss, not the empty display. */
export function learningSheetLayoutSecondary(node: LearningSheetTextSource): string {
  if (!isLearningSheetBlankedNode(node)) return String(node.textSecondary ?? '')
  return nodeHiddenAnswerSecondary(node) ?? ''
}

export function readLearningSheetBranchFromNode(node: DiagramNode): {
  text: string
  textSecondary?: string
  hidden?: true
  hiddenAnswer?: string
  hiddenAnswerSecondary?: string
} {
  const visibleGloss = (node.textSecondary ?? '').trim()
  if (!isLearningSheetBlankedNode(node)) {
    return visibleGloss
      ? { text: node.text ?? '', textSecondary: visibleGloss }
      : { text: node.text ?? '' }
  }
  const answer = nodeHiddenAnswer(node) ?? ''
  const answerSecondary = nodeHiddenAnswerSecondary(node) || visibleGloss
  return {
    text: answer,
    ...(answerSecondary ? { textSecondary: answerSecondary } : {}),
    hidden: true,
    hiddenAnswer: answer,
    ...(answerSecondary ? { hiddenAnswerSecondary: answerSecondary } : {}),
  }
}

/** After layout, put blank display text and hiddenAnswer back on matching nodes. */
export function stampLearningSheetBlanksFromBranches(
  branches: MindMapBranchSpec[],
  nodes: DiagramNode[]
): void {
  const byId = new Map(nodes.map((node) => [node.id, node]))

  const visit = (branch: MindMapBranchSpec): void => {
    const answer = typeof branch.hiddenAnswer === 'string' ? branch.hiddenAnswer.trim() : ''
    const uid = typeof branch.uid === 'string' ? branch.uid.trim() : ''
    const node = branch.hidden === true && answer && uid ? byId.get(uid) : undefined
    if (node) {
      const answerSecondary =
        typeof branch.hiddenAnswerSecondary === 'string' ? branch.hiddenAnswerSecondary.trim() : ''
      node.text = LEARNING_SHEET_BLANK_TEXT
      node.textSecondary = answerSecondary ? '' : node.textSecondary
      node.data = {
        ...node.data,
        hidden: true,
        hiddenAnswer: answer,
        ...(answerSecondary ? { hiddenAnswerSecondary: answerSecondary } : {}),
        label: LEARNING_SHEET_BLANK_TEXT,
        ...(answerSecondary ? { labelSecondary: '' } : {}),
      }
    }
    branch.children?.forEach(visit)
  }

  branches.forEach(visit)
}
