/**
 * Carry learning-sheet blanks across mind-map spec rebuilds (add/delete).
 */
import type { DiagramNode } from '@/types'

import type { MindMapBranchSpec } from './mindMapLegacyLayout'
import { LEARNING_SHEET_BLANK_TEXT, isLearningSheetBlankDisplayText } from './utils'

function nodeHiddenAnswer(node: DiagramNode): string | undefined {
  const raw = (node.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer
  if (typeof raw !== 'string') return undefined
  const trimmed = raw.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

function isBlanked(node: DiagramNode): boolean {
  const answer = nodeHiddenAnswer(node)
  if (!answer) return false
  const hidden = (node.data as { hidden?: boolean } | undefined)?.hidden
  return hidden === true || isLearningSheetBlankDisplayText(node.text)
}

/** Layout / numbering estimates use the answer while the node is blanked. */
export function learningSheetLayoutText(node: DiagramNode): string {
  return isBlanked(node) ? (nodeHiddenAnswer(node) ?? '') : String(node.text ?? '')
}

/** Spec `text` is the answer so layout keeps underline width. */
function nodeHiddenAnswerSecondary(node: DiagramNode): string | undefined {
  const raw = (node.data as { hiddenAnswerSecondary?: string } | undefined)?.hiddenAnswerSecondary
  if (typeof raw !== 'string') return undefined
  const trimmed = raw.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

export function readLearningSheetBranchFromNode(node: DiagramNode): {
  text: string
  textSecondary?: string
  hidden?: true
  hiddenAnswer?: string
  hiddenAnswerSecondary?: string
} {
  const visibleGloss = (node.textSecondary ?? '').trim()
  if (!isBlanked(node)) {
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
