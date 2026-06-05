import { computed } from 'vue'

import {
  estimateNodeWidth as estimateMindMapBranchWidth,
  measureBranchNodeHeight as measureMindMapBranchHeight,
} from '../specLoader/mindMap'
import { LEARNING_SHEET_PLACEHOLDER } from '../specLoader/utils'
import { emitEvent } from './events'
import type { DiagramContext } from './types'

export function useLearningSheetSlice(ctx: DiagramContext) {
  const { data } = ctx

  function isMindMap(): boolean {
    return ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map'
  }

  function mindMapEstimatedData(
    existingData: Record<string, unknown> | undefined,
    text: string
  ): Record<string, unknown> | undefined {
    if (!isMindMap()) return existingData
    return {
      ...existingData,
      estimatedWidth: estimateMindMapBranchWidth(text),
      estimatedHeight: measureMindMapBranchHeight(text),
    }
  }

  const isLearningSheet = computed(() => {
    const d = data.value as { isLearningSheet?: boolean; is_learning_sheet?: boolean } | null
    return d?.isLearningSheet === true || d?.is_learning_sheet === true
  })

  const hiddenAnswers = computed(
    () => (data.value as { hiddenAnswers?: string[] } | null)?.hiddenAnswers ?? []
  )

  function syncLearningSheetFlags(d: Record<string, unknown>, enabled: boolean): void {
    d.isLearningSheet = enabled
    if (enabled) {
      d.is_learning_sheet = true
    } else {
      delete d.is_learning_sheet
    }
  }

  function nodeHiddenAnswer(node: { data?: Record<string, unknown> }): string | undefined {
    const answer = (node.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer
    return typeof answer === 'string' && answer.trim() ? answer.trim() : undefined
  }

  function trackHiddenAnswer(d: Record<string, unknown>, originalText: string, prevAnswer?: string): void {
    let answers = (d.hiddenAnswers as string[] | undefined) ?? []
    if (prevAnswer && prevAnswer !== originalText) {
      answers = answers.map((entry) => (entry === prevAnswer ? originalText : entry))
    }
    if (!answers.includes(originalText)) {
      answers = [...answers, originalText]
    }
    d.hiddenAnswers = answers
  }

  function emptyNodeForLearningSheet(nodeId: string): boolean {
    if (!data.value?.nodes || !isLearningSheet.value) return false

    const nodeIndex = data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    const node = data.value.nodes[nodeIndex]
    const originalText = String(node.text ?? '').trim()
    const nodeData = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
    if (!originalText || originalText === LEARNING_SHEET_PLACEHOLDER || nodeData?.hidden) return false

    const d = data.value as Record<string, unknown>
    trackHiddenAnswer(d, originalText, nodeHiddenAnswer(node))

    data.value.nodes[nodeIndex] = {
      ...node,
      text: LEARNING_SHEET_PLACEHOLDER,
      data: {
        ...mindMapEstimatedData(node.data as Record<string, unknown>, LEARNING_SHEET_PLACEHOLDER),
        hidden: true,
        hiddenAnswer: originalText,
      },
    }

    emitEvent('diagram:node_updated', { nodeId, updates: { text: LEARNING_SHEET_PLACEHOLDER } })
    return true
  }

  function setLearningSheetMode(enabled: boolean): void {
    if (!data.value) return
    const d = data.value as Record<string, unknown>
    syncLearningSheetFlags(d, enabled)
    if (enabled && !d.hiddenAnswers) {
      d.hiddenAnswers = []
    }
  }

  function restoreFromLearningSheetMode(): void {
    const dv = data.value
    if (!dv?.nodes || !isLearningSheet.value) return

    const d = dv as Record<string, unknown>

    dv.nodes.forEach((node, idx) => {
      const originalText = nodeHiddenAnswer(node)
      if (!originalText) return
      dv.nodes[idx] = {
        ...node,
        text: originalText,
        data: {
          ...mindMapEstimatedData(node.data as Record<string, unknown>, originalText),
          hidden: false,
          hiddenAnswer: originalText,
        },
      }
      emitEvent('diagram:node_updated', { nodeId: node.id, updates: { text: originalText } })
    })

    syncLearningSheetFlags(d, false)
  }

  function applyLearningSheetView(): void {
    const dv = data.value
    if (!dv?.nodes) return

    const d = dv as Record<string, unknown>

    dv.nodes.forEach((node, idx) => {
      const originalText = nodeHiddenAnswer(node)
      if (!originalText) return
      dv.nodes[idx] = {
        ...node,
        text: LEARNING_SHEET_PLACEHOLDER,
        data: {
          ...mindMapEstimatedData(
            node.data as Record<string, unknown>,
            LEARNING_SHEET_PLACEHOLDER
          ),
          hidden: true,
          hiddenAnswer: originalText,
        },
      }
      emitEvent('diagram:node_updated', {
        nodeId: node.id,
        updates: { text: LEARNING_SHEET_PLACEHOLDER },
      })
    })

    syncLearningSheetFlags(d, true)
  }

  function hasPreservedLearningSheet(): boolean {
    if (!data.value?.nodes) return false
    return data.value.nodes.some((n) => nodeHiddenAnswer(n) !== undefined)
  }

  return {
    isLearningSheet,
    hiddenAnswers,
    emptyNodeForLearningSheet,
    setLearningSheetMode,
    restoreFromLearningSheetMode,
    applyLearningSheetView,
    hasPreservedLearningSheet,
  }
}
