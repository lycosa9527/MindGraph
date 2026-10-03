import { computed } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import type { Connection, DiagramNode } from '@/types'
import { nodesInLearningSheetReadingOrder } from '@/utils/learningSheetAnswerOrder'

import {
  LEARNING_SHEET_BLANK_TEXT,
  LEARNING_SHEET_RANDOM_BLANK_RATIO,
  isLearningSheetBlankDisplayText,
  pickLearningSheetRandomNodeIds,
} from '../specLoader/utils'
import { emitCtxEvent } from './events'
import { reconcileAfterHistoryRestore } from './historyRestore'
import type { DiagramContext } from './types'

export function useLearningSheetSlice(ctx: DiagramContext) {
  const { data } = ctx

  function isMindMap(): boolean {
    return ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map'
  }

  /**
   * Size the layout is already using. Measured box wins over a text estimate.
   * Does not remeasure or restack — blanking must not move siblings.
   */
  function mindMapBoxAlreadyUsed(
    nodeId: string,
    nodeData: Record<string, unknown> | undefined
  ): { estimatedWidth: number; estimatedHeight: number } | undefined {
    if (!isMindMap()) return undefined
    const measuredW = ctx.mindMapNodeWidths.value[nodeId]
    const measuredH = ctx.mindMapNodeHeights.value[nodeId]
    const existing = nodeData as { estimatedWidth?: number; estimatedHeight?: number } | undefined
    const width =
      typeof measuredW === 'number' && measuredW > 0 ? measuredW : existing?.estimatedWidth
    const height =
      typeof measuredH === 'number' && measuredH > 0 ? measuredH : existing?.estimatedHeight
    if (typeof width !== 'number' || width <= 0 || typeof height !== 'number' || height <= 0) {
      return undefined
    }
    return { estimatedWidth: width, estimatedHeight: height }
  }

  const isLearningSheet = computed(() => {
    const d = data.value as { isLearningSheet?: boolean; is_learning_sheet?: boolean } | null
    return d?.isLearningSheet === true || d?.is_learning_sheet === true
  })

  const hiddenAnswers = computed(
    () => (data.value as { hiddenAnswers?: string[] } | null)?.hiddenAnswers ?? []
  )

  const learningSheetShowAnswers = computed(() => {
    const d = data.value as {
      learningSheetShowAnswers?: boolean
      learning_sheet_show_answers?: boolean
    } | null
    if (d?.learningSheetShowAnswers === false || d?.learning_sheet_show_answers === false) {
      return false
    }
    return true
  })

  function notifyLearningSheetChanged(): void {
    if (!ctx.emitDiagramEvents) return
    eventBus.emit('diagram:learning_sheet_changed', {})
  }

  function setLearningSheetShowAnswers(show: boolean): void {
    if (!data.value) return
    const d = data.value as Record<string, unknown>
    d.learningSheetShowAnswers = show
    if (show) {
      delete d.learning_sheet_show_answers
    } else {
      d.learning_sheet_show_answers = false
    }
    notifyLearningSheetChanged()
  }

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

  interface LearningSheetBaselineSnapshot {
    nodeIds: string[]
    textsById: Record<string, string>
    nodes?: DiagramNode[]
    connections?: Connection[]
  }

  function cloneDiagramNodeForBaseline(node: DiagramNode): DiagramNode {
    const cloned = JSON.parse(JSON.stringify(node)) as DiagramNode
    const answer = nodeHiddenAnswer(cloned)
    const nodeData = cloned.data as Record<string, unknown> | undefined
    if (answer) {
      cloned.text = answer
      if (nodeData) {
        nodeData.label = answer
        delete nodeData.hidden
        delete nodeData.hiddenAnswer
      }
    } else if (nodeData) {
      delete nodeData.hidden
      delete nodeData.hiddenAnswer
    }
    return cloned
  }

  function readLearningSheetBaseline(
    diagramData: Record<string, unknown>
  ): LearningSheetBaselineSnapshot | null {
    const raw = diagramData.learningSheetBaseline ?? diagramData.learning_sheet_baseline
    if (!raw || typeof raw !== 'object') return null
    const record = raw as Record<string, unknown>
    const nodeIds = record.nodeIds ?? record.node_ids
    const textsById = record.textsById ?? record.texts_by_id
    if (!Array.isArray(nodeIds) || typeof textsById !== 'object' || textsById === null) {
      return null
    }
    const nodesRaw = record.nodes
    const connectionsRaw = record.connections
    return {
      nodeIds: nodeIds.map(String),
      textsById: textsById as Record<string, string>,
      nodes: Array.isArray(nodesRaw)
        ? (JSON.parse(JSON.stringify(nodesRaw)) as DiagramNode[])
        : undefined,
      connections: Array.isArray(connectionsRaw)
        ? (JSON.parse(JSON.stringify(connectionsRaw)) as Connection[])
        : undefined,
    }
  }

  function nodeOriginalTextForBaseline(node: {
    id: string
    text?: string
    data?: Record<string, unknown>
  }): string {
    const answer = nodeHiddenAnswer(node)
    if (answer) return answer
    const nodeData = node.data as { label?: string } | undefined
    const primary = String(node.text ?? nodeData?.label ?? '').trim()
    const secondary = String((node as { textSecondary?: string }).textSecondary ?? '').trim()
    if (!secondary) return primary
    return `${primary}\u0000${secondary}`
  }

  function captureLearningSheetBaseline(): void {
    if (!data.value?.nodes) return
    const d = data.value as Record<string, unknown>
    const nodes = data.value.nodes.map(cloneDiagramNodeForBaseline)
    const connections = JSON.parse(JSON.stringify(data.value.connections ?? [])) as Connection[]
    const nodeIds = nodes.map((node) => node.id)
    const textsById: Record<string, string> = {}
    for (const node of nodes) {
      textsById[node.id] = nodeOriginalTextForBaseline(node)
    }
    d.learningSheetBaseline = { nodeIds, textsById, nodes, connections }
  }

  function ensureLearningSheetBaseline(): void {
    if (!data.value) return
    const d = data.value as Record<string, unknown>
    if (readLearningSheetBaseline(d)) return
    captureLearningSheetBaseline()
  }

  function clearLearningSheetBaseline(): void {
    if (!data.value) return
    const d = data.value as Record<string, unknown>
    delete d.learningSheetBaseline
    delete d.learning_sheet_baseline
  }

  /**
   * Write an inline edit into the node's real content while the worksheet is on.
   * A knocked-out node is filled with the new wording, and its reference chip is dropped
   * so the answer list cannot keep the previous text. Re-blanking stores the new wording.
   * A visible node drops a stale answer key when the wording changes, so re-applying
   * the sheet cannot put the old answer back. The pre-worksheet baseline stays unchanged.
   */
  function commitLearningSheetNodeContent(
    nodeId: string,
    text: string,
    textSecondary?: string
  ): boolean {
    if (!isLearningSheet.value || !data.value?.nodes) return false
    const trimmed = text.trim()
    if (!trimmed || isLearningSheetBlankDisplayText(trimmed)) return false

    const nodeIndex = data.value.nodes.findIndex((node) => node.id === nodeId)
    if (nodeIndex === -1) return false

    const node = data.value.nodes[nodeIndex]
    const nodeData = { ...(node.data as Record<string, unknown> | undefined) }
    const wasBlanked = isNodeBlankedForLearningSheet(nodeId)
    const storedAnswer = nodeHiddenAnswer(node) ?? ''
    const storedSecondary =
      typeof nodeData.hiddenAnswerSecondary === 'string'
        ? nodeData.hiddenAnswerSecondary.trim()
        : ''
    const visibleSecondary = String(node.textSecondary ?? '').trim()
    const canonical = wasBlanked || storedAnswer ? storedAnswer : String(node.text ?? '').trim()
    const canonicalSecondary = wasBlanked || storedSecondary ? storedSecondary : visibleSecondary
    const nextSecondary = textSecondary !== undefined ? textSecondary.trim() : canonicalSecondary
    const textEdited = trimmed !== canonical
    const secondaryEdited = textSecondary !== undefined && nextSecondary !== canonicalSecondary
    if (!textEdited && !secondaryEdited) {
      if (wasBlanked && !isLearningSheetBlankDisplayText(String(node.text ?? ''))) {
        data.value.nodes[nodeIndex] = {
          ...node,
          text: LEARNING_SHEET_BLANK_TEXT,
          textSecondary: '',
          data: {
            ...nodeData,
            hidden: true,
            hiddenAnswer: storedAnswer,
            ...(storedSecondary ? { hiddenAnswerSecondary: storedSecondary } : {}),
            label: LEARNING_SHEET_BLANK_TEXT,
            labelSecondary: '',
          },
        }
      }
      return false
    }

    const applySecondary = textSecondary !== undefined || storedSecondary.length > 0
    delete nodeData.hidden
    delete nodeData.hiddenAnswer
    delete nodeData.hiddenAnswerSecondary
    nodeData.label = trimmed
    if (applySecondary) {
      nodeData.labelSecondary = nextSecondary
    }

    data.value.nodes[nodeIndex] = {
      ...node,
      text: trimmed,
      ...(applySecondary ? { textSecondary: nextSecondary } : {}),
      data: nodeData,
    }

    reconcileHiddenAnswersFromBlankedNodes()
    return true
  }

  function learningSheetHasUserDiagramEdits(): boolean {
    if (!isLearningSheet.value || !data.value?.nodes?.length) return false
    const d = data.value as Record<string, unknown>
    const baseline = readLearningSheetBaseline(d)
    if (!baseline) return false

    const currentIds = data.value.nodes.map((node) => node.id)
    if (currentIds.length !== baseline.nodeIds.length) return true
    const baselineIdSet = new Set(baseline.nodeIds)
    for (const id of currentIds) {
      if (!baselineIdSet.has(id)) return true
    }

    for (const node of data.value.nodes) {
      const baselineText = baseline.textsById[node.id]
      if (baselineText === undefined) continue
      const currentText = isNodeBlankedForLearningSheet(node.id)
        ? (nodeHiddenAnswer(node) ?? '')
        : nodeOriginalTextForBaseline(node)
      if (currentText !== baselineText) return true
    }
    return false
  }

  /** Restore replaces the live diagram with the pre-worksheet snapshot. */
  function learningSheetRestoreOverwritesDiagram(): boolean {
    if (!isLearningSheet.value || !data.value?.nodes?.length) return false
    if (data.value.nodes.some((node) => isNodeBlankedForLearningSheet(node.id))) return true
    return learningSheetHasUserDiagramEdits()
  }

  function isNodeBlankedForLearningSheet(nodeId: string): boolean {
    const node = data.value?.nodes?.find((n) => n.id === nodeId)
    if (!node) return false
    const nodeData = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
    if (nodeData?.hidden === true && nodeHiddenAnswer(node) !== undefined) {
      return true
    }
    const text = String(node.text ?? '').trim()
    return isLearningSheetBlankDisplayText(text) && nodeHiddenAnswer(node) !== undefined
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
      textSecondary:
        typeof (node.data as { hiddenAnswerSecondary?: string } | undefined)
          ?.hiddenAnswerSecondary === 'string'
          ? (node.data as { hiddenAnswerSecondary?: string }).hiddenAnswerSecondary
          : node.textSecondary,
      data: {
        ...(node.data as Record<string, unknown>),
        hidden: false,
        hiddenAnswer: originalText,
        label: originalText,
        labelSecondary:
          typeof (node.data as { hiddenAnswerSecondary?: string } | undefined)
            ?.hiddenAnswerSecondary === 'string'
            ? (node.data as { hiddenAnswerSecondary?: string }).hiddenAnswerSecondary
            : (node.textSecondary ?? ''),
      },
    }

    reconcileHiddenAnswersFromBlankedNodes()

    emitCtxEvent(ctx, 'diagram:node_updated', { nodeId, updates: { text: originalText } })
    if (ctx.emitDiagramEvents) {
      eventBus.emit('node:text_updated', { nodeId, text: originalText })
    }
    return true
  }

  function emptyNodeForLearningSheet(nodeId: string): boolean {
    if (!data.value?.nodes || !isLearningSheet.value) return false

    const nodeIndex = data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    const node = data.value.nodes[nodeIndex]
    const nodeData = node.data as
      { hidden?: boolean; hiddenAnswer?: string; label?: string } | undefined
    const originalText = String(node.text ?? nodeData?.label ?? '').trim()
    const originalSecondary = String(node.textSecondary ?? '').trim()
    if (!originalText || isLearningSheetBlankDisplayText(originalText) || nodeData?.hidden) {
      return false
    }

    const nodeRecord = node.data as Record<string, unknown> | undefined
    data.value.nodes[nodeIndex] = {
      ...node,
      text: LEARNING_SHEET_BLANK_TEXT,
      textSecondary: '',
      data: {
        ...nodeRecord,
        ...mindMapBoxAlreadyUsed(nodeId, nodeRecord),
        hidden: true,
        hiddenAnswer: originalText,
        ...(originalSecondary ? { hiddenAnswerSecondary: originalSecondary } : {}),
        label: LEARNING_SHEET_BLANK_TEXT,
        labelSecondary: '',
      },
    }

    reconcileHiddenAnswersFromBlankedNodes()

    emitCtxEvent(ctx, 'diagram:node_updated', {
      nodeId,
      updates: { text: LEARNING_SHEET_BLANK_TEXT },
    })
    if (ctx.emitDiagramEvents) {
      eventBus.emit('node:text_updated', { nodeId, text: LEARNING_SHEET_BLANK_TEXT })
    }
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
    const ordered = nodesInLearningSheetReadingOrder(
      data.value.nodes,
      data.value.connections ?? [],
      ctx.type.value,
      data.value._mindmap_branch_numbering === true
    )
    for (const node of ordered) {
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
      ensureLearningSheetBaseline()
    } else {
      d.hiddenAnswers = []
      clearLearningSheetBaseline()
    }
    notifyLearningSheetChanged()
  }

  function restoreFromLearningSheetMode(): void {
    const dv = data.value
    if (!dv?.nodes || !isLearningSheet.value) return

    const d = dv as Record<string, unknown>
    const baseline = readLearningSheetBaseline(d)

    if (baseline?.nodes?.length) {
      dv.nodes = baseline.nodes.map(cloneDiagramNodeForBaseline)
      dv.connections = JSON.parse(JSON.stringify(baseline.connections ?? [])) as Connection[]
      reconcileAfterHistoryRestore(ctx)
      syncLearningSheetFlags(d, false)
      d.hiddenAnswers = []
      clearLearningSheetBaseline()
      notifyLearningSheetChanged()
      return
    }

    dv.nodes.forEach((node, idx) => {
      const originalText = nodeHiddenAnswer(node)
      if (!originalText) return
      dv.nodes[idx] = {
        ...node,
        text: originalText,
        data: {
          ...(node.data as Record<string, unknown>),
          hidden: false,
          hiddenAnswer: originalText,
          label: originalText,
        },
      }
      emitCtxEvent(ctx, 'diagram:node_updated', {
        nodeId: node.id,
        updates: { text: originalText },
      })
    })

    syncLearningSheetFlags(d, false)
    d.hiddenAnswers = []
    clearLearningSheetBaseline()
    notifyLearningSheetChanged()
  }

  function applyLearningSheetView(): void {
    const dv = data.value
    if (!dv?.nodes) return

    const d = dv as Record<string, unknown>
    ensureLearningSheetBaseline()

    dv.nodes.forEach((node, idx) => {
      const originalText = nodeHiddenAnswer(node)
      if (!originalText) return
      const nodeRecord = node.data as Record<string, unknown> | undefined
      dv.nodes[idx] = {
        ...node,
        text: LEARNING_SHEET_BLANK_TEXT,
        data: {
          ...nodeRecord,
          ...mindMapBoxAlreadyUsed(node.id, nodeRecord),
          hidden: true,
          hiddenAnswer: originalText,
          label: LEARNING_SHEET_BLANK_TEXT,
        },
      }
      emitCtxEvent(ctx, 'diagram:node_updated', {
        nodeId: node.id,
        updates: { text: LEARNING_SHEET_BLANK_TEXT },
      })
    })

    reconcileHiddenAnswersFromBlankedNodes()
    syncLearningSheetFlags(d, true)
    notifyLearningSheetChanged()
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
      const {
        hidden: _hidden,
        hiddenAnswer: _answer,
        hiddenAnswerSecondary: _answerSecondary,
        ...rest
      } = nodeData
      dv.nodes[idx] = {
        ...node,
        data: rest,
      }
    })

    syncLearningSheetFlags(d, false)
    notifyLearningSheetChanged()
  }

  /**
   * Knock out a share of hideable nodes on the live canvas.
   * Keeps current positions and measured boxes — does not reload the spec.
   */
  function applyRandomLearningSheetBlanks(
    percentage: number = LEARNING_SHEET_RANDOM_BLANK_RATIO
  ): number {
    const nodes = data.value?.nodes
    const diagramType = ctx.type.value
    if (!nodes?.length || !diagramType) return 0
    const ids = pickLearningSheetRandomNodeIds(nodes, diagramType, percentage)
    setLearningSheetMode(true)
    let count = 0
    for (const nodeId of ids) {
      if (emptyNodeForLearningSheet(nodeId)) count += 1
    }
    return count
  }

  function hasBlankedLearningSheetNodes(): boolean {
    if (!data.value?.nodes?.length) return false
    return data.value.nodes.some((node) => isNodeBlankedForLearningSheet(node.id))
  }

  /** Temporarily fill knocked-out nodes with answers (for PDF answer page); restores after run. */
  async function runWithLearningSheetAnswersRevealed<T>(run: () => T | Promise<T>): Promise<T> {
    const dv = data.value
    if (!dv?.nodes?.length) {
      return run()
    }

    const savedShowAnswers = learningSheetShowAnswers.value
    setLearningSheetShowAnswers(false)

    const snapshots: Array<{ idx: number; node: (typeof dv.nodes)[number] }> = []
    dv.nodes.forEach((node, idx) => {
      if (!isNodeBlankedForLearningSheet(node.id)) return
      const answer = nodeHiddenAnswer(node)
      if (!answer) return
      snapshots.push({
        idx,
        node: { ...node, data: { ...(node.data as Record<string, unknown>) } },
      })
      dv.nodes[idx] = {
        ...node,
        text: answer,
        data: {
          ...(node.data as Record<string, unknown>),
          label: answer,
          hidden: false,
        },
      }
      emitCtxEvent(ctx, 'diagram:node_updated', { nodeId: node.id, updates: { text: answer } })
    })

    const restore = (): void => {
      snapshots.forEach(({ idx, node }) => {
        dv.nodes[idx] = node
        emitCtxEvent(ctx, 'diagram:node_updated', {
          nodeId: node.id,
          updates: { text: node.text ?? LEARNING_SHEET_BLANK_TEXT },
        })
      })
      setLearningSheetShowAnswers(savedShowAnswers)
    }

    try {
      const result = await run()
      restore()
      return result
    } catch (error) {
      restore()
      throw error
    }
  }

  return {
    isLearningSheet,
    hiddenAnswers,
    learningSheetShowAnswers,
    setLearningSheetShowAnswers,
    isNodeBlankedForLearningSheet,
    emptyNodeForLearningSheet,
    restoreNodeFromLearningSheet,
    toggleLearningSheetNodeBlank,
    setLearningSheetMode,
    reconcileHiddenAnswersFromBlankedNodes,
    restoreFromLearningSheetMode,
    applyLearningSheetView,
    applyRandomLearningSheetBlanks,
    hasPreservedLearningSheet,
    clearLearningSheetPreservation,
    hasBlankedLearningSheetNodes,
    runWithLearningSheetAnswersRevealed,
    ensureLearningSheetBaseline,
    learningSheetHasUserDiagramEdits,
    learningSheetRestoreOverwritesDiagram,
    commitLearningSheetNodeContent,
  }
}
