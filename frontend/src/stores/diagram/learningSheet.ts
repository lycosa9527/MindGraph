import { computed } from 'vue'

import { LEARNING_SHEET_PLACEHOLDER } from '../specLoader/utils'

import { emitEvent } from './events'
import type { DiagramContext } from './types'

export function useLearningSheetSlice(ctx: DiagramContext) {
  const { data } = ctx

  const isLearningSheet = computed(() => {
    const d = data.value as { isLearningSheet?: boolean; is_learning_sheet?: boolean } | null
    return d?.isLearningSheet === true || d?.is_learning_sheet === true
  })

  const hiddenAnswers = computed(
    () => (data.value as { hiddenAnswers?: string[] } | null)?.hiddenAnswers ?? [],
  )

  function emptyNodeForLearningSheet(nodeId: string): boolean {
    if (!data.value?.nodes || !isLearningSheet.value) return false

    const nodeIndex = data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    const node = data.value.nodes[nodeIndex]
    const originalText = String(node.text ?? '').trim()
    if (!originalText || node.data?.hidden) return false

    const d = data.value as Record<string, unknown>
    const existingAnswers = (d.hiddenAnswers as string[] | undefined) ?? []
    d.hiddenAnswers = [...existingAnswers, originalText]

    data.value.nodes[nodeIndex] = {
      ...node,
      text: LEARNING_SHEET_PLACEHOLDER,
      data: {
        ...node.data,
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
    d.isLearningSheet = enabled
    if (enabled && !d.hiddenAnswers) {
      d.hiddenAnswers = []
    }
  }

  function restoreFromLearningSheetMode(): void {
    const dv = data.value
    if (!dv?.nodes || !isLearningSheet.value) return

    const d = dv as Record<string, unknown>

    dv.nodes.forEach((node, idx) => {
      const nodeData = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
      if (nodeData?.hidden === true && nodeData?.hiddenAnswer) {
        const originalText = nodeData.hiddenAnswer
        dv.nodes[idx] = {
          ...node,
          text: originalText,
          data: {
            ...node.data,
            hidden: true,
            hiddenAnswer: originalText,
          },
        }
        emitEvent('diagram:node_updated', { nodeId: node.id, updates: { text: originalText } })
      }
    })

    d.isLearningSheet = false
  }

  function applyLearningSheetView(): void {
    const dv = data.value
    if (!dv?.nodes) return

    const d = dv as Record<string, unknown>

    dv.nodes.forEach((node, idx) => {
      const nodeData = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
      if (nodeData?.hidden === true && nodeData?.hiddenAnswer) {
        dv.nodes[idx] = {
          ...node,
          text: LEARNING_SHEET_PLACEHOLDER,
          data: {
            ...node.data,
            hidden: true,
            hiddenAnswer: nodeData.hiddenAnswer,
          },
        }
        emitEvent('diagram:node_updated', {
          nodeId: node.id,
          updates: { text: LEARNING_SHEET_PLACEHOLDER },
        })
      }
    })

    d.isLearningSheet = true
  }

  function hasPreservedLearningSheet(): boolean {
    if (!data.value?.nodes) return false
    return data.value.nodes.some(
      (n) => (n.data as { hidden?: boolean; hiddenAnswer?: string })?.hidden === true,
    )
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
