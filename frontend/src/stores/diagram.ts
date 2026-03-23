/**
 * Diagram Store - Pinia store for diagram state management.
 * Thin wiring layer that assembles modular slices.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { eventBus } from '@/composables/useEventBus'
import type { DiagramData, DiagramNode, DiagramType, HistoryEntry } from '@/types'

import { useConceptMapRelationshipStore } from './conceptMapRelationship'
import { useBraceMapOpsSlice } from './diagram/braceMapOps'
import { useBubbleMapOpsSlice } from './diagram/bubbleMapOps'
import { useConnectionManagementSlice } from './diagram/connectionManagement'
import { VALID_DIAGRAM_TYPES } from './diagram/constants'
import { useCopyPasteSlice } from './diagram/copyPaste'
import { useCustomPositionsSlice } from './diagram/customPositions'
import { useDoubleBubbleMapOpsSlice } from './diagram/doubleBubbleMapOps'
import { useFlowMapOpsSlice } from './diagram/flowMapOps'
import { useHistorySlice } from './diagram/history'
import { useLearningSheetSlice } from './diagram/learningSheet'
import { useMindMapOpsSlice } from './diagram/mindMapOps'
import { useMultiFlowLayoutSlice } from './diagram/multiFlowLayout'
import { useNodeManagementSlice } from './diagram/nodeManagement'
import { useNodeStylesSlice } from './diagram/nodeStyles'
import { useNodeSwapOpsSlice } from './diagram/nodeSwapOps'
import { useSelectionSlice } from './diagram/selection'
import { useSpecIOSlice } from './diagram/specIO'
import { useTitleSlice } from './diagram/titleManagement'
import { useTreeMapOpsSlice } from './diagram/treeMapOps'
import type { DiagramContext, MindMapCurveExtents } from './diagram/types'
import { useVueFlowIntegrationSlice } from './diagram/vueFlowIntegration'

export { subscribeToDiagramEvents } from './diagram/events'
export type {
  DiagramEvent,
  DiagramEventType,
  LoadFromSpecOptions,
  MindMapCurveExtents,
} from './diagram/types'

export const useDiagramStore = defineStore('diagram', () => {
  // Core state refs
  const type = ref<DiagramType | null>(null)
  const sessionId = ref<string | null>(null)
  const data = ref<DiagramData | null>(null)
  const selectedNodes = ref<string[]>([])
  const history = ref<HistoryEntry[]>([])
  const historyIndex = ref(-1)
  const title = ref<string>('')
  const isUserEditedTitle = ref<boolean>(false)
  const copiedNodes = ref<DiagramNode[]>([])
  const topicNodeWidth = ref<number | null>(null)
  const mindMapCurveExtentBaseline = ref<MindMapCurveExtents | null>(null)
  const nodeWidths = ref<Record<string, number>>({})
  const multiFlowMapRecalcTrigger = ref(0)
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
    history,
    historyIndex,
    title,
    isUserEditedTitle,
    copiedNodes,
    mindMapCurveExtentBaseline,
    nodeWidths,
    topicNodeWidth,
    multiFlowMapRecalcTrigger,
    sessionEditCount,
    collabSessionActive,
    collabForeignLockedNodeIds,
  } as DiagramContext

  // ?? Phase 2 slices ??
  const historySlice = useHistorySlice(ctx)
  ctx.pushHistory = historySlice.pushHistory

  const selectionSlice = useSelectionSlice(ctx)
  const customPositionsSlice = useCustomPositionsSlice(ctx)
  const nodeStylesSlice = useNodeStylesSlice(ctx)
  const learningSheetSlice = useLearningSheetSlice(ctx)
  const titleSlice = useTitleSlice(ctx)

  const { pushHistory, canUndo, canRedo, undo, redo, clearHistory, clearRedoStack } =
    historySlice
  const {
    selectNodes,
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
  const { saveNodeStyle, getNodeStyle, clearNodeStyle, clearAllNodeStyles, applyStylePreset } =
    nodeStylesSlice
  const {
    isLearningSheet,
    hiddenAnswers,
    emptyNodeForLearningSheet,
    setLearningSheetMode,
    restoreFromLearningSheetMode,
    applyLearningSheetView,
    hasPreservedLearningSheet,
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
    if (oldType !== newType) {
      eventBus.emit('diagram:type_changed', { diagramType: newType })
    }
    return true
  }

  ctx.setDiagramType = setDiagramType
  ctx.resetSessionEditCount = resetSessionEditCount

  const multiFlowLayoutSlice = useMultiFlowLayoutSlice(ctx)
  const { setTopicNodeWidth, setNodeWidth } = multiFlowLayoutSlice
  ctx.setNodeWidth = setNodeWidth

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
    updateConnectionArrowheadsForNode,
    toggleConnectionArrowhead,
  } = connectionSlice
  ctx.addConnection = addConnection

  const nodeManagementSlice = useNodeManagementSlice(ctx)
  const { addNode, updateNode, emptyNode, removeNode } = nodeManagementSlice
  ctx.addNode = addNode

  const copyPasteSlice = useCopyPasteSlice(ctx)
  const { canPaste, copySelectedNodes, pasteNodesAt } = copyPasteSlice

  const vueFlowSlice = useVueFlowIntegrationSlice(ctx)
  const {
    vueFlowNodes,
    vueFlowEdges,
    updateNodePosition,
    updateNodesFromVueFlow,
    syncFromVueFlow,
  } = vueFlowSlice

  const nodeSwapSlice = useNodeSwapOpsSlice(ctx)
  const { getNodeGroupIds, moveNodeBySwap } = nodeSwapSlice

  // ?? Remaining inline computed / actions ??

  const nodeCount = computed(() => data.value?.nodes?.length ?? 0)

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

  function reset(): void {
    type.value = null
    sessionId.value = null
    data.value = null
    selectedNodes.value = []
    history.value = []
    historyIndex.value = -1
    mindMapCurveExtentBaseline.value = null
    useConceptMapRelationshipStore().clearAll()
    title.value = ''
    isUserEditedTitle.value = false
  }

  return {
    type,
    sessionId,
    data,
    selectedNodes,
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
    effectiveTitle,
    vueFlowNodes,
    vueFlowEdges,
    setDiagramType,
    setSessionId,
    updateDiagram,
    selectNodes,
    clearSelection,
    addToSelection,
    removeFromSelection,
    pushHistory,
    undo,
    redo,
    clearHistory,
    clearRedoStack,
    collabSessionActive,
    setCollabSessionActive,
    collabForeignLockedNodeIds,
    setCollabForeignLockedNodeIds,
    updateNode,
    emptyNodeForLearningSheet,
    emptyNode,
    setLearningSheetMode,
    restoreFromLearningSheetMode,
    applyLearningSheetView,
    hasPreservedLearningSheet,
    addNode,
    addConnection,
    updateConnectionLabel,
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
    getMindMapDescendantIds,
    copySelectedNodes,
    pasteNodesAt,
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
    loadFromSpec,
    loadDefaultTemplate,
    mergeGranularUpdate,
    getSpecForSave,
    getDoubleBubbleSpecFromData,
    addDoubleBubbleMapNode,
    removeDoubleBubbleMapNodes,
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
  }
})
