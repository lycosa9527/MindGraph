/**
 * Diagram session factory — assembles modular slices for one diagram instance.
 * The Pinia `diagram` store wraps an edit session; Showcase creates a readonly session.
 */
import { computed, reactive, ref, type UnwrapNestedRefs } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import type { DiagramData, DiagramNode, DiagramType, HistoryEntry } from '@/types'

import { useConceptMapRelationshipStore } from '../conceptMapRelationship'
import type { MindMapCanvasMode } from '../ui'
import { useBraceMapOpsSlice } from './braceMapOps'
import { useBubbleMapOpsSlice } from './bubbleMapOps'
import { useConnectionManagementSlice } from './connectionManagement'
import { VALID_DIAGRAM_TYPES } from './constants'
import { useCopyPasteSlice } from './copyPaste'
import { useCustomPositionsSlice } from './customPositions'
import {
  EDITOR_DIAGRAM_VUE_FLOW_ID,
  type DiagramViewBus,
  adaptGlobalEventBusAsViewBus,
  createDiagramViewBus,
} from './diagramViewBus'
import { useDoubleBubbleMapOpsSlice } from './doubleBubbleMapOps'
import { useFlowMapOpsSlice } from './flowMapOps'
import { useHistorySlice } from './history'
import { reconcileAfterHistoryRestore as reconcileDiagramAfterHistoryRestore } from './historyRestore'
import { useLearningSheetSlice } from './learningSheet'
import { reconcileMindMapCanvasModeSwitch } from './mindMapCanvasModeSwitch'
import { syncMindMapStoreLayoutPositions } from './mindMapDisplayLayout'
import { useMindMapLayoutSlice } from './mindMapLayout'
import {
  cancelMindMapPendingInlineEdit,
  clearMindMapEditingNodeId,
  setMindMapEditingNodeId,
  useMindMapOpsSlice,
} from './mindMapOps'
import { createMindMapRecalcScheduler } from './mindMapRecalcScheduler'
import { resyncMindMapConnectionStrokeColorsForActiveMode } from './mindMapStylePreservation'
import { useMultiFlowLayoutSlice } from './multiFlowLayout'
import { useNodeDimensionSlice } from './nodeDimensionSlice'
import { useNodeManagementSlice } from './nodeManagement'
import { useNodeStylesSlice } from './nodeStyles'
import { useNodeSwapOpsSlice } from './nodeSwapOps'
import { useSelectionSlice } from './selection'
import { useSpecIOSlice } from './specIO'
import { useTitleSlice } from './titleManagement'
import { useTreeMapOpsSlice } from './treeMapOps'
import type { DiagramContext, MindMapCurveExtents } from './types'
import { useVueFlowIntegrationSlice } from './vueFlowIntegration'

export type DiagramSessionMode = 'edit' | 'readonly'

export type CreateDiagramSessionOptions = {
  mode?: DiagramSessionMode
  vueFlowId?: string
  viewBus?: DiagramViewBus
  /** When false, do not emit diagram:* / type_changed onto the global app bus. */
  emitDiagramEvents?: boolean
}

export function createDiagramSession(options: CreateDiagramSessionOptions = {}) {
  const mode: DiagramSessionMode = options.mode ?? 'edit'
  const isReadonly = ref(mode === 'readonly')
  const vueFlowId = options.vueFlowId ?? EDITOR_DIAGRAM_VUE_FLOW_ID
  const emitDiagramEvents = options.emitDiagramEvents ?? mode === 'edit'
  const viewBus: DiagramViewBus =
    options.viewBus ??
    (mode === 'edit' ? adaptGlobalEventBusAsViewBus(eventBus) : createDiagramViewBus())

  // Core state refs
  const type = ref<DiagramType | null>(null)
  const sessionId = ref<string | null>(null)
  const data = ref<DiagramData | null>(null)
  const selectedNodes = ref<string[]>([])
  const selectedConnectionId = ref<string | null>(null)
  const history = ref<HistoryEntry[]>([])
  const historyIndex = ref(-1)
  const title = ref<string>('')
  const isUserEditedTitle = ref<boolean>(false)
  const copiedNodes = ref<DiagramNode[]>([])
  const topicNodeWidth = ref<number | null>(null)
  const mindMapCurveExtentBaseline = ref<MindMapCurveExtents | null>(null)
  const mindMapTopicActualWidth = ref<number | null>(null)
  const nodeWidths = ref<Record<string, number>>({})
  const multiFlowMapRecalcTrigger = ref(0)
  const mindMapNodeWidths = ref<Record<string, number>>({})
  const mindMapNodeHeights = ref<Record<string, number>>({})
  const mindMapRecalcTrigger = ref(0)
  const mindMapTopicBranchGaps = ref<{ left: number; right: number } | null>(null)
  const mindMapPendingEditNodeId = ref<string | null>(null)
  const mindMapEditingNodeId = ref<string | null>(null)
  const mindMapPreserveIncomingY = ref(false)
  const mindMapPreserveIncomingYNodeId = ref<string | null>(null)
  const mindMapBulkLoading = ref(false)
  const nodeDimensions = ref<Record<string, { width: number; height: number }>>({})
  const layoutRecalcTrigger = ref(0)
  const sessionEditCount = ref(0)
  const collabSessionActive = ref(false)
  const collabForeignLockedNodeIds = ref<Set<string>>(new Set())

  function resetSessionEditCount(): void {
    sessionEditCount.value = 0
  }

  function setCollabSessionActive(active: boolean): void {
    collabSessionActive.value = active
    if (!active) {
      collabForeignLockedNodeIds.value = new Set()
    }
  }

  function setCollabForeignLockedNodeIds(nodeIds: string[]): void {
    collabForeignLockedNodeIds.value = new Set(nodeIds)
  }

  // Shared context (two-phase: refs now, cross-deps wired after slice init)
  const ctx = {
    type,
    data,
    selectedNodes,
    selectedConnectionId,
    history,
    historyIndex,
    title,
    isUserEditedTitle,
    copiedNodes,
    mindMapCurveExtentBaseline,
    mindMapTopicActualWidth,
    nodeWidths,
    topicNodeWidth,
    multiFlowMapRecalcTrigger,
    mindMapNodeWidths,
    mindMapNodeHeights,
    mindMapRecalcTrigger,
    mindMapTopicBranchGaps,
    mindMapPendingEditNodeId,
    mindMapEditingNodeId,
    mindMapPreserveIncomingY,
    mindMapPreserveIncomingYNodeId,
    mindMapBulkLoading,
    nodeDimensions,
    layoutRecalcTrigger,
    sessionEditCount,
    collabSessionActive,
    collabForeignLockedNodeIds,
    isReadonly,
    vueFlowId,
    viewBus,
    emitDiagramEvents,
  } as DiagramContext

  ctx.scheduleMindMapRecalc = createMindMapRecalcScheduler(type, mindMapRecalcTrigger, () =>
    syncMindMapStoreLayoutPositions(ctx)
  )

  // ?? Phase 2 slices ??
  const historySlice = useHistorySlice(ctx)
  ctx.pushHistory = historySlice.pushHistory

  const selectionSlice = useSelectionSlice(ctx)
  const customPositionsSlice = useCustomPositionsSlice(ctx)
  const nodeStylesSlice = useNodeStylesSlice(ctx)
  const learningSheetSlice = useLearningSheetSlice(ctx)
  const titleSlice = useTitleSlice(ctx)

  const {
    pushHistory,
    canUndo,
    canRedo,
    undo,
    redo,
    clearHistory,
    clearRedoStack,
    seedHistoryBaseline,
    seedHistoryBaselineIfEmpty,
  } = historySlice
  const {
    selectNodes,
    selectConnection,
    clearSelection,
    addToSelection,
    removeFromSelection,
    hasSelection,
    selectedNodeData,
  } = selectionSlice
  const {
    saveCustomPosition,
    hasCustomPosition,
    getCustomPosition,
    clearCustomPosition,
    resetToAutoLayout,
  } = customPositionsSlice
  const {
    saveNodeStyle,
    getNodeStyle,
    clearNodeStyle,
    clearAllNodeStyles,
    applyStylePreset,
    applyMindMapAppearance,
  } = nodeStylesSlice
  const {
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
  } = learningSheetSlice
  const {
    effectiveTitle,
    getTopicNodeText,
    setTitle,
    initTitle,
    resetTitle,
    shouldAutoUpdateTitle,
  } = titleSlice

  ctx.clearCustomPosition = clearCustomPosition
  ctx.clearNodeStyle = clearNodeStyle
  ctx.removeFromSelection = removeFromSelection
  ctx.saveCustomPosition = saveCustomPosition

  // ?? Phase 3 slices (diagram-type ops) ??
  const mindMapOpsSlice = useMindMapOpsSlice(ctx)
  const bubbleMapOpsSlice = useBubbleMapOpsSlice(ctx)
  const braceMapOpsSlice = useBraceMapOpsSlice(ctx)
  const doubleBubbleMapOpsSlice = useDoubleBubbleMapOpsSlice(ctx)
  const flowMapOpsSlice = useFlowMapOpsSlice(ctx)
  const treeMapOpsSlice = useTreeMapOpsSlice(ctx)

  const {
    addMindMapBranch,
    addMindMapChild,
    removeMindMapNodes,
    getMindMapDescendantIds,
    moveMindMapBranch,
    addMindMapSibling,
    insertMindMapSiblingsFromLines,
    insertMindMapParentBranch,
    performMindMapDirectionalAdd,
    getMindMapStructureMode,
    setMindMapStructureMode,
    toggleMindMapCollapse,
    expandMindMapPathToNode,
    applyMindMapSubgraphPreview,
    restoreMindMapSubgraphSnapshot,
    clearMindMapSubgraphPreviewTags,
    pasteMindMapClipboardBranches,
  } = mindMapOpsSlice
  const { removeBubbleMapNodes } = bubbleMapOpsSlice
  const { addBraceMapPart, removeBraceMapNodes } = braceMapOpsSlice
  const { addDoubleBubbleMapNode, removeDoubleBubbleMapNodes } = doubleBubbleMapOpsSlice
  const { toggleFlowMapOrientation, addFlowMapStep, addFlowMapSubstep } = flowMapOpsSlice
  const {
    removeTreeMapNodes,
    getTreeMapDescendantIds,
    moveTreeMapBranch,
    addTreeMapCategory,
    addTreeMapChild,
  } = treeMapOpsSlice

  ctx.getMindMapDescendantIds = getMindMapDescendantIds
  ctx.getTreeMapDescendantIds = getTreeMapDescendantIds

  // ?? Phase 4 slices ??

  // Inline actions that stay in diagram.ts (small, used by context wiring)
  function setDiagramType(newType: DiagramType): boolean {
    if (!VALID_DIAGRAM_TYPES.includes(newType)) {
      console.error(`Invalid diagram type: ${newType}`)
      return false
    }
    const oldType = type.value
    type.value = newType
    if (oldType !== newType && emitDiagramEvents) {
      eventBus.emit('diagram:type_changed', { diagramType: newType })
    }
    return true
  }

  ctx.setDiagramType = setDiagramType
  ctx.resetSessionEditCount = resetSessionEditCount

  const nodeDimensionSlice = useNodeDimensionSlice(ctx)
  const {
    setNodeDimensions: setNodeDimensionsSlice,
    clearNodeDimensions,
    getNodeDimension,
    setExpectedNodeCount,
  } = nodeDimensionSlice
  ctx.setExpectedNodeCount = setExpectedNodeCount

  const multiFlowLayoutSlice = useMultiFlowLayoutSlice(ctx)
  const { setTopicNodeWidth, setNodeWidth } = multiFlowLayoutSlice
  ctx.setNodeWidth = setNodeWidth

  const mindMapLayoutSlice = useMindMapLayoutSlice(ctx)
  const {
    armMindMapMeasureBatch,
    setMindMapTopicWidth,
    setMindMapTopicMeasured,
    setMindMapNodeWidth: setMindMapNodeWidthSlice,
    setMindMapNodeDimensions,
    clearMindMapNodeWidths,
  } = mindMapLayoutSlice
  ctx.armMindMapMeasureBatch = armMindMapMeasureBatch

  const specIOSlice = useSpecIOSlice(ctx)
  const {
    loadFromSpec,
    getDoubleBubbleSpecFromData,
    getSpecForSave,
    buildFlowMapSpecFromNodes,
    loadDefaultTemplate,
    mergeGranularUpdate,
  } = specIOSlice
  ctx.loadFromSpec = loadFromSpec
  ctx.getDoubleBubbleSpecFromData = getDoubleBubbleSpecFromData
  ctx.buildFlowMapSpecFromNodes = buildFlowMapSpecFromNodes

  const connectionSlice = useConnectionManagementSlice(ctx)
  const {
    addConnection,
    updateConnectionLabel,
    removeConnection: removeConceptMapConnection,
    updateConnectionArrowheadsForNode,
    toggleConnectionArrowhead,
  } = connectionSlice
  ctx.addConnection = addConnection

  const nodeManagementSlice = useNodeManagementSlice(ctx)
  const { addNode, updateNode, emptyNode, removeNode } = nodeManagementSlice
  ctx.addNode = addNode

  const copyPasteSlice = useCopyPasteSlice(ctx, {
    removeMindMapNodes,
    removeTreeMapNodes,
    removeBraceMapNodes,
    removeNode,
    pasteMindMapClipboardBranches,
  })
  const {
    canPaste,
    copySelectedNodes,
    cutSelectedNodes,
    pasteClipboardAt,
    pasteNodesAt,
    clearCopiedNodes,
  } = copyPasteSlice

  const vueFlowSlice = useVueFlowIntegrationSlice(ctx)
  const {
    vueFlowNodes,
    vueFlowEdges,
    mindMapOrthogonalSiblingsByGroup,
    updateNodePosition,
    updateNodesFromVueFlow,
    syncFromVueFlow,
  } = vueFlowSlice

  const nodeSwapSlice = useNodeSwapOpsSlice(ctx)
  const { getNodeGroupIds, moveNodeBySwap } = nodeSwapSlice

  // ?? Remaining inline computed / actions ??

  const nodeCount = computed(() => data.value?.nodes?.length ?? 0)

  function resyncMindMapConnectionStrokeColors(): void {
    if (
      !resyncMindMapConnectionStrokeColorsForActiveMode(
        type.value,
        data.value?.nodes,
        data.value?.connections
      )
    ) {
      return
    }
    mindMapRecalcTrigger.value += 1
  }

  function reconcileMindMapCanvasMode(
    previousMode: MindMapCanvasMode,
    newMode: MindMapCanvasMode
  ): boolean {
    return reconcileMindMapCanvasModeSwitch(ctx, previousMode, newMode)
  }

  function setSessionId(id: string): boolean {
    if (!id || typeof id !== 'string' || id.trim() === '') {
      console.error('Invalid session ID')
      return false
    }
    sessionId.value = id
    return true
  }

  function updateDiagram(
    updates: Partial<{ type: DiagramType; sessionId: string; data: DiagramData }>
  ): boolean {
    if (updates.type && !VALID_DIAGRAM_TYPES.includes(updates.type)) {
      console.error(`Invalid diagram type: ${updates.type}`)
      return false
    }
    if (updates.sessionId !== undefined) {
      if (typeof updates.sessionId !== 'string' || updates.sessionId.trim() === '') {
        console.error('Invalid session ID')
        return false
      }
    }
    if (updates.type) type.value = updates.type
    if (updates.sessionId) sessionId.value = updates.sessionId
    if (updates.data) data.value = updates.data
    return true
  }

  function setConceptMapFocusQuestion(text: string): void {
    if (!data.value || type.value !== 'concept_map') return
    const trimmed = text.trim()
    if (!trimmed) return
    data.value = { ...data.value, focus_question: trimmed }
  }

  function reconcileAfterHistoryRestore(): void {
    reconcileDiagramAfterHistoryRestore(ctx)
  }

  function reset(): void {
    cancelMindMapPendingInlineEdit(ctx)
    type.value = null
    sessionId.value = null
    data.value = null
    selectedNodes.value = []
    selectedConnectionId.value = null
    history.value = []
    historyIndex.value = -1
    copiedNodes.value = []
    topicNodeWidth.value = null
    nodeWidths.value = {}
    multiFlowMapRecalcTrigger.value = 0
    mindMapCurveExtentBaseline.value = null
    mindMapTopicActualWidth.value = null
    mindMapNodeWidths.value = {}
    mindMapNodeHeights.value = {}
    mindMapRecalcTrigger.value = 0
    mindMapTopicBranchGaps.value = null
    mindMapPendingEditNodeId.value = null
    mindMapEditingNodeId.value = null
    mindMapPreserveIncomingY.value = false
    mindMapPreserveIncomingYNodeId.value = null
    mindMapBulkLoading.value = false
    clearNodeDimensions()
    layoutRecalcTrigger.value = 0
    sessionEditCount.value = 0
    collabSessionActive.value = false
    collabForeignLockedNodeIds.value = new Set()
    // Readonly preview sessions must not clear the editor's concept-map picker.
    if (emitDiagramEvents && !isReadonly.value) {
      useConceptMapRelationshipStore().clearAll()
    }
    title.value = ''
    isUserEditedTitle.value = false
  }

  function dispose(): void {
    if (mode === 'readonly') {
      viewBus.clear()
    }
  }

  return {
    mode,
    isReadonly,
    vueFlowId,
    viewBus,
    emitDiagramEvents,
    dispose,
    type,
    sessionId,
    data,
    selectedNodes,
    selectedConnectionId,
    history,
    historyIndex,
    title,
    isUserEditedTitle,
    sessionEditCount,
    resetSessionEditCount,
    canUndo,
    canRedo,
    nodeCount,
    hasSelection,
    canPaste,
    selectedNodeData,
    isLearningSheet,
    hiddenAnswers,
    learningSheetShowAnswers,
    effectiveTitle,
    vueFlowNodes,
    vueFlowEdges,
    mindMapOrthogonalSiblingsByGroup,
    setDiagramType,
    setSessionId,
    updateDiagram,
    selectNodes,
    selectConnection,
    clearSelection,
    addToSelection,
    removeFromSelection,
    pushHistory,
    seedHistoryBaseline,
    seedHistoryBaselineIfEmpty,
    undo,
    redo,
    clearHistory,
    clearRedoStack,
    reconcileAfterHistoryRestore,
    collabSessionActive,
    setCollabSessionActive,
    collabForeignLockedNodeIds,
    setCollabForeignLockedNodeIds,
    updateNode,
    emptyNodeForLearningSheet,
    isNodeBlankedForLearningSheet,
    restoreNodeFromLearningSheet,
    toggleLearningSheetNodeBlank,
    emptyNode,
    setLearningSheetMode,
    setLearningSheetShowAnswers,
    reconcileHiddenAnswersFromBlankedNodes,
    restoreFromLearningSheetMode,
    applyLearningSheetView,
    hasPreservedLearningSheet,
    clearLearningSheetPreservation,
    hasBlankedLearningSheetNodes,
    runWithLearningSheetAnswersRevealed,
    addNode,
    addConnection,
    updateConnectionLabel,
    removeConceptMapConnection,
    toggleConnectionArrowhead,
    updateConnectionArrowheadsForNode,
    removeNode,
    removeBubbleMapNodes,
    addBraceMapPart,
    removeBraceMapNodes,
    addMindMapBranch,
    addMindMapChild,
    removeMindMapNodes,
    moveMindMapBranch,
    addMindMapSibling,
    insertMindMapSiblingsFromLines,
    insertMindMapParentBranch,
    performMindMapDirectionalAdd,
    getMindMapStructureMode,
    setMindMapStructureMode,
    toggleMindMapCollapse,
    expandMindMapPathToNode,
    applyMindMapSubgraphPreview,
    restoreMindMapSubgraphSnapshot,
    clearMindMapSubgraphPreviewTags,
    pasteMindMapClipboardBranches,
    getMindMapDescendantIds,
    resyncMindMapConnectionStrokeColors,
    reconcileMindMapCanvasMode,
    copySelectedNodes,
    cutSelectedNodes,
    pasteClipboardAt,
    pasteNodesAt,
    clearCopiedNodes,
    reset,
    updateNodePosition,
    updateNodesFromVueFlow,
    syncFromVueFlow,
    saveCustomPosition,
    hasCustomPosition,
    getCustomPosition,
    clearCustomPosition,
    resetToAutoLayout,
    saveNodeStyle,
    getNodeStyle,
    clearNodeStyle,
    clearAllNodeStyles,
    applyStylePreset,
    applyMindMapAppearance,
    loadFromSpec,
    loadDefaultTemplate,
    mergeGranularUpdate,
    getSpecForSave,
    getDoubleBubbleSpecFromData,
    addDoubleBubbleMapNode,
    removeDoubleBubbleMapNodes,
    buildFlowMapSpecFromNodes,
    addFlowMapStep,
    addFlowMapSubstep,
    toggleFlowMapOrientation,
    addTreeMapCategory,
    addTreeMapChild,
    moveTreeMapBranch,
    getTreeMapDescendantIds,
    removeTreeMapNodes,
    getNodeGroupIds,
    moveNodeBySwap,
    getTopicNodeText,
    setTitle,
    initTitle,
    resetTitle,
    shouldAutoUpdateTitle,
    setTopicNodeWidth,
    setNodeWidth,
    setConceptMapFocusQuestion,
    setMindMapTopicWidth,
    setMindMapTopicMeasured,
    setMindMapNodeWidth: setMindMapNodeWidthSlice,
    setMindMapNodeDimensions,
    clearMindMapNodeWidths,
    mindMapTopicActualWidth,
    mindMapNodeWidths,
    mindMapNodeHeights,
    mindMapRecalcTrigger,
    mindMapTopicBranchGaps,
    mindMapPendingEditNodeId,
    mindMapEditingNodeId,
    cancelMindMapPendingInlineEdit: (reason?: string) =>
      cancelMindMapPendingInlineEdit(ctx, reason),
    setMindMapEditingNodeId: (nodeId: string | null) => setMindMapEditingNodeId(ctx, nodeId),
    clearMindMapEditingNodeId: (nodeId?: string) => clearMindMapEditingNodeId(ctx, nodeId),
    mindMapPreserveIncomingY,
    mindMapPreserveIncomingYNodeId,
    mindMapBulkLoading,
    nodeDimensions,
    layoutRecalcTrigger,
    setNodeDimensions: setNodeDimensionsSlice,
    clearNodeDimensions,
    getNodeDimension,
    setExpectedNodeCount,
  }
}

/** Raw session: refs are not auto-unwrapped (Pinia setup return shape). */
export type DiagramSessionRaw = ReturnType<typeof createDiagramSession>

/**
 * Public session API — same property access as Pinia (`store.type` is the value, not Ref).
 * Preview sessions use {@link asDiagramSession}; the editor Pinia store matches this shape.
 */
export type DiagramSession = UnwrapNestedRefs<DiagramSessionRaw>

/** Wrap a raw session so template/script access matches Pinia auto-unwrap. */
export function asDiagramSession(raw: DiagramSessionRaw): DiagramSession {
  return reactive(raw)
}
