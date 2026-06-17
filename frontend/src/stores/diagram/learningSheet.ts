import { computed } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
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
    text: string,
    nodeId?: string
  ): Record<string, unknown> | undefined {
    if (!isMindMap()) return existingData
    return {
      ...existingData,
      estimatedWidth: estimateMindMapBranchWidth(text, nodeId),
      estimatedHeight: measureMindMapBranchHeight(text, nodeId),
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

  function isNodeBlankedForLearningSheet(nodeId: string): boolean {
    const node = data.value?.nodes?.find((n) => n.id === nodeId)
    if (!node) return false
    const nodeData = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
    const text = String(node.text ?? '').trim()
    return (
      nodeData?.hidden === true ||
      (text === LEARNING_SHEET_PLACEHOLDER && nodeHiddenAnswer(node) !== undefined)
    )
  }

  function restoreNodeFromLearningSheet(nodeId: string): boolean {
    if (!data.value?.nodes || !isLearningSheet.value) return false

    const nodeIndex = data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    const node = data.value.nodes[nodeIndex]
    const originalText = nodeHiddenAnswer(node)
    if (!originalText) return false

    data.value.nodes[nodeIndex] = {
      ...node,
      text: originalText,
      data: {
        ...mindMapEstimatedData(node.data as Record<string, unknown>, originalText, nodeId),
        hidden: false,
        hiddenAnswer: originalText,
      },
    }

    reconcileHiddenAnswersFromBlankedNodes()

    emitEvent('diagram:node_updated', { nodeId, updates: { text: originalText } })
    eventBus.emit('node:text_updated', { nodeId, text: originalText })
    return true
  }

  function emptyNodeForLearningSheet(nodeId: string): boolean {
    if (!data.value?.nodes || !isLearningSheet.value) return false

    const nodeIndex = data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    const node = data.value.nodes[nodeIndex]
    const nodeData = node.data as { hidden?: boolean; hiddenAnswer?: string; label?: string } | undefined
    const originalText = String(node.text ?? nodeData?.label ?? '').trim()
    if (!originalText || originalText === LEARNING_SHEET_PLACEHOLDER || nodeData?.hidden) return false

    data.value.nodes[nodeIndex] = {
      ...node,
      text: LEARNING_SHEET_PLACEHOLDER,
      data: {
        ...mindMapEstimatedData(node.data as Record<string, unknown>, LEARNING_SHEET_PLACEHOLDER, nodeId),
        hidden: true,
        hiddenAnswer: originalText,
      },
    }

    reconcileHiddenAnswersFromBlankedNodes()

    emitEvent('diagram:node_updated', { nodeId, updates: { text: LEARNING_SHEET_PLACEHOLDER } })
    eventBus.emit('node:text_updated', { nodeId, text: LEARNING_SHEET_PLACEHOLDER })
    return true
  }

  function toggleLearningSheetNodeBlank(nodeId: string): 'blanked' | 'restored' | 'skipped' {
    if (!data.value?.nodes || !isLearningSheet.value) return 'skipped'
    if (isNodeBlankedForLearningSheet(nodeId)) {
      return restoreNodeFromLearningSheet(nodeId) ? 'restored' : 'skipped'
    }
    return emptyNodeForLearningSheet(nodeId) ? 'blanked' : 'skipped'
  }

  function reconcileHiddenAnswersFromBlankedNodes(): void {
    if (!data.value?.nodes) return
    const d = data.value as Record<string, unknown>
    const answers: string[] = []
    for (const node of data.value.nodes) {
      if (!isNodeBlankedForLearningSheet(node.id)) continue
      const answer = nodeHiddenAnswer(node)
      if (answer && !answers.includes(answer)) {
        answers.push(answer)
      }
    }
    d.hiddenAnswers = answers
  }

  function setLearningSheetMode(enabled: boolean): void {
    if (!data.value) return
    const d = data.value as Record<string, unknown>
    syncLearningSheetFlags(d, enabled)
    if (enabled) {
      reconcileHiddenAnswersFromBlankedNodes()
    } else {
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
          ...mindMapEstimatedData(node.data as Record<string, unknown>, originalText, node.id),
          hidden: false,
          hiddenAnswer: originalText,
        },
      }
      emitEvent('diagram:node_updated', { nodeId: node.id, updates: { text: originalText } })
    })

    syncLearningSheetFlags(d, false)
    d.hiddenAnswers = []
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
            LEARNING_SHEET_PLACEHOLDER,
            node.id
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

  function clearLearningSheetPreservation(): void {
    const dv = data.value
    if (!dv?.nodes) return

    const d = dv as Record<string, unknown>
    d.hiddenAnswers = []

    dv.nodes.forEach((node, idx) => {
      const nodeData = node.data as Record<string, unknown> | undefined
      if (!nodeData?.hiddenAnswer) return
      const { hidden: _hidden, hiddenAnswer: _answer, ...rest } = nodeData
      dv.nodes[idx] = {
        ...node,
        data: rest,
      }
    })

    syncLearningSheetFlags(d, false)
  }

  return {
    isLearningSheet,
    hiddenAnswers,
    isNodeBlankedForLearningSheet,
    emptyNodeForLearningSheet,
    restoreNodeFromLearningSheet,
    toggleLearningSheetNodeBlank,
    setLearningSheetMode,
    reconcileHiddenAnswersFromBlankedNodes,
    restoreFromLearningSheetMode,
    applyLearningSheetView,
    hasPreservedLearningSheet,
    clearLearningSheetPreservation,
  }
}
