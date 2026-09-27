import { computed } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import { nodesInLearningSheetReadingOrder } from '@/utils/learningSheetAnswerOrder'
import { mindMapBranchNumberMapFromData } from '@/utils/mindMapBranchNumbering'

import {
  estimateNodeWidth as estimateMindMapBranchWidth,
  estimateNumberedBranchWidth,
  measureBranchNodeHeight as measureMindMapBranchHeight,
  measureNumberedBranchHeight,
} from '../specLoader/mindMap'
import { LEARNING_SHEET_BLANK_TEXT, isLearningSheetBlankDisplayText } from '../specLoader/utils'
import { emitCtxEvent } from './events'
import { reconcileAfterHistoryRestore } from './historyRestore'
import type { DiagramContext } from './types'

export function useLearningSheetSlice(ctx: DiagramContext) {
  const { data } = ctx

  function isMindMap(): boolean {
    return ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map'
  }

  /** Layout size from answer text; keeps pre-blank estimates when already set. */
  function mindMapLayoutEstimates(
    existingData: Record<string, unknown> | undefined,
    layoutText: string,
    nodeId?: string,
    nodeStyle?: NodeStyle
  ): Record<string, unknown> | undefined {
    if (!isMindMap()) return existingData
    const existing = existingData as
      { estimatedWidth?: number; estimatedHeight?: number } | undefined
    const numberMap = mindMapBranchNumberMapFromData(data.value)
    const prefix = nodeId ? (numberMap.get(nodeId) ?? '') : ''
    const fromText = {
      estimatedWidth: nodeId
        ? estimateNumberedBranchWidth(layoutText, prefix, nodeId, nodeStyle)
        : estimateMindMapBranchWidth(layoutText, nodeId, nodeStyle),
      estimatedHeight: nodeId
        ? measureNumberedBranchHeight(layoutText, prefix, nodeId, nodeStyle)
        : measureMindMapBranchHeight(layoutText, nodeId, nodeStyle),
    }
    return {
      ...existingData,
      estimatedWidth:
        typeof existing?.estimatedWidth === 'number' && existing.estimatedWidth > 0
          ? Math.max(existing.estimatedWidth, fromText.estimatedWidth)
          : fromText.estimatedWidth,
      estimatedHeight:
        typeof existing?.estimatedHeight === 'number' && existing.estimatedHeight > 0
          ? Math.max(existing.estimatedHeight, fromText.estimatedHeight)
          : fromText.estimatedHeight,
    }
  }

  function preserveMindMapBlankedLayoutSize(
    nodeId: string,
    layoutWidth: number,
    layoutHeight: number
  ): void {
    if (!isMindMap()) return
    const prevW = ctx.mindMapNodeWidths.value[nodeId]
    const prevH = ctx.mindMapNodeHeights.value[nodeId]
    const width = Math.max(prevW ?? 0, layoutWidth)
    const height = Math.max(prevH ?? 0, layoutHeight)
    if (width > 0) ctx.mindMapNodeWidths.value[nodeId] = width
    if (height > 0) ctx.mindMapNodeHeights.value[nodeId] = height
    ctx.scheduleMindMapRecalc()
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
    return String(node.text ?? nodeData?.label ?? '').trim()
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
      if (isNodeBlankedForLearningSheet(node.id)) continue
      const baselineText = baseline.textsById[node.id]
      if (baselineText === undefined) continue
      if (nodeOriginalTextForBaseline(node) !== baselineText) return true
    }
    return false
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

    delete ctx.mindMapNodeWidths.value[nodeId]
    delete ctx.mindMapNodeHeights.value[nodeId]

    data.value.nodes[nodeIndex] = {
      ...node,
      text: originalText,
      data: {
        ...mindMapLayoutEstimates(
          node.data as Record<string, unknown>,
          originalText,
          nodeId,
          node.style
        ),
        hidden: false,
        hiddenAnswer: originalText,
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
    if (!originalText || isLearningSheetBlankDisplayText(originalText) || nodeData?.hidden) {
      return false
    }

    const layoutData = mindMapLayoutEstimates(
      node.data as Record<string, unknown>,
      originalText,
      nodeId,
      node.style
    ) as { estimatedWidth?: number; estimatedHeight?: number }

    data.value.nodes[nodeIndex] = {
      ...node,
      text: LEARNING_SHEET_BLANK_TEXT,
      data: {
        ...layoutData,
        hidden: true,
        hiddenAnswer: originalText,
        label: LEARNING_SHEET_BLANK_TEXT,
      },
    }

    if (layoutData.estimatedWidth && layoutData.estimatedHeight) {
      preserveMindMapBlankedLayoutSize(
        nodeId,
        layoutData.estimatedWidth,
        layoutData.estimatedHeight
      )
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

  function restoreBlankedNodesFromHiddenAnswers(): void {
    const dv = data.value
    if (!dv?.nodes) return

    dv.nodes.forEach((node, idx) => {
      const originalText = nodeHiddenAnswer(node)
      if (!originalText) return
      dv.nodes[idx] = {
        ...node,
        text: originalText,
        data: {
          ...mindMapLayoutEstimates(
            node.data as Record<string, unknown>,
            originalText,
            node.id,
            node.style
          ),
          hidden: false,
          hiddenAnswer: originalText,
        },
      }
      delete ctx.mindMapNodeWidths.value[node.id]
      delete ctx.mindMapNodeHeights.value[node.id]
      emitCtxEvent(ctx, 'diagram:node_updated', {
        nodeId: node.id,
        updates: { text: originalText },
      })
    })
  }

  function restoreFromLearningSheetMode(): void {
    const dv = data.value
    if (!dv?.nodes || !isLearningSheet.value) return

    const d = dv as Record<string, unknown>
    const baseline = readLearningSheetBaseline(d)

    if (baseline?.nodes?.length) {
      dv.nodes = baseline.nodes.map(cloneDiagramNodeForBaseline)
      dv.connections = JSON.parse(
        JSON.stringify(baseline.connections ?? [])
      ) as Connection[]
      reconcileAfterHistoryRestore(ctx)
    } else {
      restoreBlankedNodesFromHiddenAnswers()
    }

    syncLearningSheetFlags(d, false)
    d.hiddenAnswers = []
    clearLearningSheetBaseline()
    notifyLearningSheetChanged()
  }

  function applyLearningSheetView(): void {
    const dv = data.value
    if (!dv?.nodes) return

    const d = dv as Record<string, unknown>

    dv.nodes.forEach((node, idx) => {
      const originalText = nodeHiddenAnswer(node)
      if (!originalText) return
      const layoutData = mindMapLayoutEstimates(
        node.data as Record<string, unknown>,
        originalText,
        node.id,
        node.style
      ) as { estimatedWidth?: number; estimatedHeight?: number }

      dv.nodes[idx] = {
        ...node,
        text: LEARNING_SHEET_BLANK_TEXT,
        data: {
          ...layoutData,
          hidden: true,
          hiddenAnswer: originalText,
          label: LEARNING_SHEET_BLANK_TEXT,
        },
      }
      if (layoutData.estimatedWidth && layoutData.estimatedHeight) {
        preserveMindMapBlankedLayoutSize(
          node.id,
          layoutData.estimatedWidth,
          layoutData.estimatedHeight
        )
      }
      emitCtxEvent(ctx, 'diagram:node_updated', {
        nodeId: node.id,
        updates: { text: LEARNING_SHEET_BLANK_TEXT },
      })
    })

    syncLearningSheetFlags(d, true)
    ensureLearningSheetBaseline()
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
      const { hidden: _hidden, hiddenAnswer: _answer, ...rest } = nodeData
      dv.nodes[idx] = {
        ...node,
        data: rest,
      }
    })

    syncLearningSheetFlags(d, false)
    clearLearningSheetBaseline()
    notifyLearningSheetChanged()
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
    hasPreservedLearningSheet,
    clearLearningSheetPreservation,
    hasBlankedLearningSheetNodes,
    runWithLearningSheetAnswersRevealed,
    ensureLearningSheetBaseline,
    learningSheetHasUserDiagramEdits,
  }
}
