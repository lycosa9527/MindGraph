<script setup lang="ts">
/**
 * CanvasPage - Full canvas editor page with Vue Flow integration
 *
 * Store cleanup on exit (onUnmounted): diagram, savedDiagrams, llmResults, panels,
 * and partial ui reset - avoids memory leaks from canvas-specific state.
 *
 * Users access this page via:
 * 1. DiagramTemplateInput - Generates on landing, then navigates here with pre-loaded diagram
 * 2. DiagramTypeGrid - "在画布中创建" → navigates here with diagram type
 *
 * The "AI生成图示" button in the toolbar uses useAutoComplete composable
 * to generate content based on the topic extracted from existing nodes.
 *
 * Auto-save functionality (event + state driven):
 * - User edits: debounced auto-save on diagram changes (2 second delay)
 * - LLM generating: skip auto-save; wait for llm:generation_completed
 * - LLM completed: flush and save once
 * - Auto-updates if diagram is already in library; auto-saves new if slots available
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import {
  AIModelSelector,
  CanvasToolbar,
  CanvasTopBar,
  ConceptMapFocusQuestionModal,
  ConceptMapLabelPicker,
  InlineRecommendationsPicker,
  ZoomControls,
} from '@/components/canvas'
import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import { MindmatePanel, NodePalettePanel } from '@/components/panels'
import {
  eventBus,
  getDefaultDiagramName,
  getNodePalette,
  getPanelCoordinator,
  useDiagramAutoSave,
  useDiagramSpecForSave,
  useEditorShortcuts,
  useInlineRecommendations,
  useInlineRecommendationsCoordinator,
  useLanguage,
  useNotifications,
  useWorkshop,
} from '@/composables'
import { INLINE_RECOMMENDATIONS_SUPPORTED_TYPES } from '@/composables/nodePalette/constants'
import { IMPORT_SPEC_KEY } from '@/config'
import { ANIMATION, PANEL, PANEL_INSET } from '@/config/uiConfig'
import {
  useAuthStore,
  useConceptMapRelationshipStore,
  useDiagramStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
  usePanelsStore,
  useUIStore,
  type LLMResult,
} from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'

const route = useRoute()
const router = useRouter()
const diagramStore = useDiagramStore()
const relationshipStore = useConceptMapRelationshipStore()
const uiStore = useUIStore()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()
const llmResultsStore = useLLMResultsStore()
const panelsStore = usePanelsStore()
const { isZh, t } = useLanguage()
const notify = useNotifications()
const { activeEntry: relationshipActiveEntry } = storeToRefs(relationshipStore)
const inlineRecStore = useInlineRecommendationsStore()
const { activeNodeId: inlineRecActiveNodeId } = storeToRefs(inlineRecStore)

// Hide zoom/pan when concept map label picker or inline recommendations picker is showing
const showZoomControls = computed(
  () =>
    !(
      (diagramStore.type === 'concept_map' && relationshipActiveEntry.value) ||
      inlineRecActiveNodeId.value
    )
)

const conceptMapFocusQuestionDisplay = computed((): string | null => {
  if (diagramStore.type !== 'concept_map' || !diagramStore.data) return null
  const fq = diagramStore.data.focus_question
  if (typeof fq !== 'string' || !fq.trim()) return null
  return fq.trim()
})

const showConceptMapFocusGate = computed(
  () =>
    diagramStore.type === 'concept_map' &&
    Boolean(diagramStore.data) &&
    !conceptMapFocusQuestionDisplay.value
)

function handleConceptMapFocusConfirmed(text: string): void {
  diagramStore.setConceptMapFocusQuestion(text)
}

const inlineRecCoordinator = useInlineRecommendationsCoordinator()
const { startRecommendations } = useInlineRecommendations()

function isNodeEligibleForInlineRec(node: { id?: string; type?: string }): boolean {
  const dt = diagramStore.type === 'mind_map' ? 'mindmap' : diagramStore.type
  if (
    !dt ||
    !(INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(dt)
  )
    return false
  const nid = node.id ?? ''
  if (dt === 'mindmap') {
    return (
      nid.startsWith('branch-l-1-') ||
      nid.startsWith('branch-r-1-') ||
      nid.startsWith('branch-l-2-') ||
      nid.startsWith('branch-r-2-')
    )
  }
  if (dt === 'flow_map') {
    return nid.startsWith('flow-step-') || nid.startsWith('flow-substep-')
  }
  if (dt === 'tree_map') {
    return (
      nid === 'dimension-label' ||
      /^tree-cat-\d+$/.test(nid) ||
      /^tree-leaf-/.test(nid)
    )
  }
  if (dt === 'brace_map') {
    return (
      nid === 'dimension-label' ||
      node.type === 'brace' ||
      nid.startsWith('brace-')
    )
  }
  if (dt === 'circle_map') {
    return nid.startsWith('context-')
  }
  if (dt === 'bubble_map') {
    return nid.startsWith('bubble-')
  }
  if (dt === 'double_bubble_map') {
    return (
      nid.startsWith('similarity-') ||
      nid.startsWith('left-diff-') ||
      nid.startsWith('right-diff-')
    )
  }
  if (dt === 'multi_flow_map') {
    return nid.startsWith('cause-') || nid.startsWith('effect-')
  }
  if (dt === 'bridge_map') {
    return (
      nid === 'dimension-label' ||
      (nid.startsWith('pair-') && (nid.endsWith('-left') || nid.endsWith('-right')))
    )
  }
  return false
}

function handleNodeDoubleClick(_node: { id?: string; type?: string }): void {
  // Double-click only enters edit mode. Inline recommendations are triggered by Tab
  // when user is editing a node (see node_editor:tab_pressed listener).
}

// Canvas zoom for ZoomControls sync (updated via view:zoom_changed)
const canvasZoom = ref<number | null>(null)

// Hand tool: when active, left-click drag pans instead of moving nodes
const handToolActive = ref(false)

// Presentation mode: browser fullscreen, only top bar + bottom controls visible
const isPresentationMode = ref(false)
const canvasPageRef = ref<HTMLElement | null>(null)

// Auto-save: event-driven, config-based (useDiagramAutoSave)
const diagramAutoSave = useDiagramAutoSave()

// Auto-save status text next to file name (slot-full message or "已自动保存 12:34")
const autoSavedStatusText = computed(() => {
  if (!authStore.isAuthenticated) return null
  // Slots full + new diagram (not saved): show space-full message
  if (
    savedDiagramsStore.isSlotsFullyUsed &&
    !savedDiagramsStore.activeDiagramId
  ) {
    return t(
      'editor.slotsFull',
      isZh.value
        ? '空间已满，暂无法自动保存。请删除现有图示以释放空间。'
        : 'Space full, auto-save not available at the moment. Please delete existing diagrams to free more space.'
    )
  }
  const at = diagramAutoSave.lastSavedAt.value
  if (!at) return null
  const timeStr = at.toLocaleTimeString(isZh.value ? 'zh-CN' : 'en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
  return t('editor.autoSavedAt', isZh.value ? '已自动保存 {time}' : 'Auto-saved at {time}').replace(
    '{time}',
    timeStr
  )
})

// When slots full + new diagram, clicking status should open slot management modal
const isSlotsFullAndNewDiagram = computed(
  () =>
    authStore.isAuthenticated &&
    savedDiagramsStore.isSlotsFullyUsed &&
    !savedDiagramsStore.activeDiagramId
)

// Workshop integration
const workshopCode = ref<string | null>(null)
const currentDiagramId = computed(() => savedDiagramsStore.activeDiagramId)

// Track previous diagram state for granular updates
let previousNodes: Array<Record<string, unknown>> = []
let previousConnections: Array<Record<string, unknown>> = []

// Calculate diff between two arrays of objects (by id)
function calculateDiff<T extends { id: string }>(oldArray: T[], newArray: T[]): T[] {
  const oldMap = new Map(oldArray.map((item) => [item.id, item]))
  const changed: T[] = []

  for (const newItem of newArray) {
    const oldItem = oldMap.get(newItem.id)
    if (!oldItem || JSON.stringify(oldItem) !== JSON.stringify(newItem)) {
      changed.push(newItem)
    }
  }

  return changed
}

// Workshop composable with granular update callbacks
const {
  sendUpdate,
  notifyNodeEditing,
  activeEditors,
  watchCode: watchWorkshopCode,
} = useWorkshop(
  workshopCode,
  currentDiagramId,
  undefined, // onUpdate (full spec - backward compat, not used)
  (nodes, connections) => {
    // Granular update handler: merge incoming changes
    if (nodes || connections) {
      diagramStore.mergeGranularUpdate(nodes, connections)
    }
  },
  (nodeId, editor) => {
    // Node editing handler: apply visual indicators
    // Visual indicators will be applied via CSS classes on node elements
    // This callback can be used to update node styles if needed
    if (editor) {
      console.log(`[Workshop] User ${editor.username} ${editor.emoji} editing node ${nodeId}`)
      // Apply visual indicator via CSS class
      applyNodeEditingIndicator(nodeId, editor)
    } else {
      console.log(`[Workshop] Node ${nodeId} editing stopped`)
      // Remove visual indicator
      removeNodeEditingIndicator(nodeId)
    }
  }
)

// Start watching for workshop code changes
watchWorkshopCode()

// Apply visual indicator to node (add CSS class and data attributes)
function applyNodeEditingIndicator(
  nodeId: string,
  editor: { color: string; emoji: string; username: string }
): void {
  nextTick(() => {
    // Vue Flow nodes use id attribute, not data-id
    const nodeElement = document.querySelector(`#${nodeId}`) as HTMLElement
    if (nodeElement) {
      nodeElement.classList.add('workshop-editing')
      nodeElement.style.setProperty('--editor-color', editor.color)
      nodeElement.setAttribute('data-editor-emoji', editor.emoji)
      nodeElement.setAttribute('data-editor-username', editor.username)
    }
  })
}

// Remove visual indicator from node
function removeNodeEditingIndicator(nodeId: string): void {
  nextTick(() => {
    const nodeElement = document.querySelector(`#${nodeId}`) as HTMLElement
    if (nodeElement) {
      nodeElement.classList.remove('workshop-editing')
      nodeElement.style.removeProperty('--editor-color')
      nodeElement.removeAttribute('data-editor-emoji')
      nodeElement.removeAttribute('data-editor-username')
    }
  })
}

// Watch activeEditors to apply/remove indicators
watch(
  () => activeEditors.value,
  (newEditors, oldEditors) => {
    // Remove indicators for nodes no longer being edited
    if (oldEditors) {
      for (const [nodeId] of oldEditors) {
        if (!newEditors.has(nodeId)) {
          removeNodeEditingIndicator(nodeId)
        }
      }
    }

    // Apply indicators for newly edited nodes
    if (newEditors) {
      for (const [nodeId, editor] of newEditors) {
        if (!oldEditors?.has(nodeId)) {
          applyNodeEditingIndicator(nodeId, editor)
        }
      }
    }
  },
  { deep: true }
)

// Watch for workshop code changes from CanvasTopBar
// Note: CanvasTopBar manages the workshop modal and emits workshopCodeChanged
// We need to sync the code here for useWorkshop
eventBus.onWithOwner(
  'workshop:code-changed',
  (data) => {
    if (data.code !== undefined) {
      workshopCode.value = data.code as string | null
    }
  },
  'CanvasPage'
)

// Track node editing via eventBus
eventBus.onWithOwner(
  'node_editor:opening',
  (data) => {
    const nodeId = (data as { nodeId: string }).nodeId
    if (nodeId && workshopCode.value) {
      notifyNodeEditing(nodeId, true)
    }
  },
  'CanvasPage'
)

// Track node editing stop via blur events (handled via InlineEditableText component)
eventBus.onWithOwner(
  'node_editor:closed',
  (data) => {
    const nodeId = (data as { nodeId: string }).nodeId
    if (nodeId && workshopCode.value) {
      notifyNodeEditing(nodeId, false)
    }
  },
  'CanvasPage'
)

// Map Chinese diagram type names to DiagramType
const diagramTypeMap: Record<string, DiagramType> = {
  圆圈图: 'circle_map',
  气泡图: 'bubble_map',
  双气泡图: 'double_bubble_map',
  树形图: 'tree_map',
  括号图: 'brace_map',
  流程图: 'flow_map',
  复流程图: 'multi_flow_map',
  桥形图: 'bridge_map',
  思维导图: 'mindmap',
  概念图: 'concept_map',
}

// Reverse map: DiagramType to Chinese name (for UI store sync)
const diagramTypeToChineseMap: Record<DiagramType, string> = {
  circle_map: '圆圈图',
  bubble_map: '气泡图',
  double_bubble_map: '双气泡图',
  tree_map: '树形图',
  brace_map: '括号图',
  flow_map: '流程图',
  multi_flow_map: '复流程图',
  bridge_map: '桥形图',
  mindmap: '思维导图',
  mind_map: '思维导图',
  concept_map: '概念图',
  diagram: '图表',
}

// Valid diagram types for URL validation and import
const VALID_DIAGRAM_TYPES: DiagramType[] = [
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
  'mindmap',
  'mind_map',
  'concept_map',
]

// Get diagram type from UI store (set before navigation)
const chartType = computed(() => uiStore.selectedChartType)

const diagramType = computed<DiagramType | null>(() => {
  if (!chartType.value) return null
  return diagramTypeMap[chartType.value] || null
})

// Diagram type for default name: from store (when loaded) or route (for new diagrams)
const diagramTypeForName = computed(
  () => (diagramStore.type as string) || (route.query.type as string) || null
)

function handleZoomChange(level: number) {
  const zoom = Math.max(0.1, Math.min(4, level / 100))
  eventBus.emit('view:zoom_set_requested', { zoom })
}

function handleZoomIn() {
  eventBus.emit('view:zoom_in_requested', {})
}

function handleZoomOut() {
  eventBus.emit('view:zoom_out_requested', {})
}

function handleFitToScreen() {
  eventBus.emit('view:fit_to_canvas_requested', { animate: true })
}

function handleHandToolToggle(active: boolean) {
  handToolActive.value = active
}

async function handleStartPresentation() {
  if (isPresentationMode.value) {
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    }
    return
  }

  if (!canvasPageRef.value) return

  try {
    await canvasPageRef.value.requestFullscreen()
  } catch (err) {
    console.warn('Fullscreen request failed:', err)
    notify.error(isZh.value ? '无法进入全屏模式' : 'Could not enter fullscreen')
  }
}

function emitFitToCanvas() {
  eventBus.emit('view:fit_to_canvas_requested', { animate: true })
}

function isTypingInInput(): boolean {
  const active = document.activeElement as HTMLElement
  return (
    active?.tagName === 'INPUT' || active?.tagName === 'TEXTAREA' || !!active?.isContentEditable
  )
}

function handleDeleteKey() {
  if (isTypingInInput()) return
  eventBus.emit('diagram:delete_selected_requested', {})
}

function handleAddNodeKey() {
  if (isTypingInInput()) return
  if (diagramStore.type === 'concept_map') return
  eventBus.emit('diagram:add_node_requested', {})
}

function handleAddBranchKey() {
  if (isTypingInInput()) return
  if (diagramStore.type === 'concept_map') return
  if (
    diagramStore.type === 'mindmap' ||
    diagramStore.type === 'mind_map' ||
    diagramStore.type === 'brace_map' ||
    diagramStore.type === 'flow_map'
  ) {
    eventBus.emit('diagram:add_branch_requested', {})
  } else {
    eventBus.emit('diagram:add_node_requested', {})
  }
}

function handleAddChildKey() {
  if (isTypingInInput()) return
  if (diagramStore.type === 'concept_map') return
  if (
    diagramStore.type === 'mindmap' ||
    diagramStore.type === 'mind_map' ||
    diagramStore.type === 'brace_map' ||
    diagramStore.type === 'flow_map'
  ) {
    eventBus.emit('diagram:add_child_requested', {})
  }
}

function handleUndoKey() {
  if (isTypingInInput()) return
  diagramStore.undo()
}

function handleRedoKey() {
  if (isTypingInInput()) return
  diagramStore.redo()
}

function handleClearNodeTextKey() {
  if (isTypingInInput()) return
  if (relationshipActiveEntry.value) return
  const selected = [...diagramStore.selectedNodes]
  if (selected.length === 0) {
    notify.warning(isZh.value ? '请先选择要清空的节点' : 'Please select a node to clear')
    return
  }
  const protectedIds = [
    'topic',
    'event',
    'flow-topic',
    'left-topic',
    'right-topic',
    'dimension-label',
    'outer-boundary',
  ]
  let clearedCount = 0
  const isLearningSheet = diagramStore.isLearningSheet

  for (const nodeId of selected) {
    if (protectedIds.includes(nodeId)) continue
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    if (node && node.type !== 'topic' && node.type !== 'center' && node.type !== 'boundary') {
      if (isLearningSheet) {
        if (diagramStore.emptyNodeForLearningSheet(nodeId)) {
          clearedCount++
        }
      } else {
        if (diagramStore.emptyNode(nodeId)) {
          clearedCount++
        }
      }
    }
  }

  if (clearedCount > 0) {
    diagramStore.pushHistory(
      isLearningSheet
        ? isZh.value
          ? '留空节点并添加答案'
          : 'Empty node and add answer'
        : isZh.value
          ? '清空节点文字'
          : 'Clear node text'
    )
    notify.success(
      isLearningSheet
        ? isZh.value
          ? `已留空 ${clearedCount} 个节点，答案已添加`
          : `Emptied ${clearedCount} node(s), added to answers`
        : isZh.value
          ? `已清空 ${clearedCount} 个节点`
          : `Cleared ${clearedCount} node(s)`
    )
    // Save immediately when emptying nodes (learning sheet answers) so state persists
    if (isLearningSheet) {
      diagramAutoSave.performSave()
    }
  } else {
    notify.warning(isZh.value ? '无法清空主题或中心节点' : 'Cannot clear topic or center nodes')
  }
}

function handleSaveKey() {
  diagramAutoSave.flush()
}

useEditorShortcuts({
  undo: handleUndoKey,
  redo: handleRedoKey,
  save: handleSaveKey,
  delete: handleDeleteKey,
  addNode: handleAddNodeKey,
  addBranch: handleAddBranchKey,
  addChild: handleAddChildKey,
  clearNodeText: handleClearNodeTextKey,
})

function handleFullscreenChange() {
  if (document.fullscreenElement) {
    isPresentationMode.value = true
    // Delay fit until layout settles after fullscreen transition
    setTimeout(emitFitToCanvas, ANIMATION.FIT_VIEWPORT_DELAY)
  } else {
    isPresentationMode.value = false
    nextTick().then(() => {
      setTimeout(emitFitToCanvas, ANIMATION.FIT_VIEWPORT_DELAY)
    })
  }
}

function handleModelChange(model: string) {
  // TODO: Handle AI model change
  console.log('Selected model:', model)
}

// Listen for zoom changes (cleaned up via removeAllListenersForOwner in onUnmounted)
eventBus.onWithOwner(
  'view:zoom_changed',
  (data) => {
    const zoom = (data as { zoom?: number }).zoom
    if (zoom != null) {
      canvasZoom.value = zoom
    }
  },
  'CanvasPage'
)

// Clear node palette when diagram changes
// - diagram:loaded: clear live state only, preserve sessions for other diagrams
// - diagram:type_changed: clear all (live state + sessions map)
eventBus.onWithOwner(
  'diagram:loaded',
  () => panelsStore.clearNodePaletteState({ clearSessions: false }),
  'CanvasPage'
)
eventBus.onWithOwner('diagram:type_changed', () => panelsStore.clearNodePaletteState(), 'CanvasPage')

// Track content edits for teacher usage analytics (add/delete/change nodes)
eventBus.onWithOwner(
  'diagram:node_added',
  () => {
    diagramStore.sessionEditCount += 1
  },
  'CanvasPage'
)
eventBus.onWithOwner(
  'diagram:node_updated',
  () => {
    diagramStore.sessionEditCount += 1
  },
  'CanvasPage'
)
eventBus.onWithOwner(
  'diagram:nodes_deleted',
  (data: { nodeIds?: string[] }) => {
    diagramStore.sessionEditCount += data?.nodeIds?.length ?? 1
  },
  'CanvasPage'
)
eventBus.onWithOwner(
  'diagram:position_changed',
  () => {
    diagramStore.sessionEditCount += 1
  },
  'CanvasPage'
)
eventBus.onWithOwner(
  'diagram:style_changed',
  () => {
    diagramStore.sessionEditCount += 1
  },
  'CanvasPage'
)
eventBus.onWithOwner(
  'diagram:operation_completed',
  (payload: { operation?: string }) => {
    if (payload?.operation === 'move_branch') diagramStore.sessionEditCount += 1
  },
  'CanvasPage'
)

// LLM generation completed + cancel on start: handled by useDiagramAutoSave

// Watch for diagram type changes in store
watch(
  () => uiStore.selectedChartType,
  () => {
    if (diagramType.value) {
      diagramStore.setDiagramType(diagramType.value)
      // Load default template if we have a type and no existing diagram
      if (!diagramStore.data) {
        // Load static default template (no AI generation)
        diagramStore.loadDefaultTemplate(diagramType.value)
      }
    }
    // If no type specified, user should go back and select one
    // The canvas will show empty state
  },
  { immediate: true }
)

// Watch for diagram ID changes (sidebar switch) - load new diagram and clear node palette
watch(
  () => route.query.diagramId,
  async (newId, oldId) => {
    if (newId && typeof newId === 'string' && newId !== oldId) {
      await loadDiagramFromLibrary(newId)
    }
  }
)

/**
 * Generate default diagram name (simple, no timestamp)
 * Format: "新圆圈图" / "New Circle Map"
 */
function generateDefaultName(): string {
  return getDefaultDiagramName(diagramTypeForName.value, isZh.value)
}

// Watch for diagram data changes to send granular updates to workshop
// Auto-save: handled internally by useDiagramAutoSave (computed fingerprint + watch)
watch(
  () => diagramStore.data,
  (newData) => {
    if (!newData) return

    // Send granular updates to workshop if active (any change including position)
    if (workshopCode.value && newData.nodes && newData.connections) {
      const changedNodes = calculateDiff(
        previousNodes as Array<{ id: string }>,
        newData.nodes as Array<{ id: string }>
      )
      const changedConnections = calculateDiff(
        previousConnections as Array<{ id: string }>,
        (newData.connections || []) as Array<{ id: string }>
      )

      if (changedNodes.length > 0 || changedConnections.length > 0) {
        sendUpdate(undefined, changedNodes, changedConnections)
      }

      previousNodes = JSON.parse(JSON.stringify(newData.nodes))
      previousConnections = JSON.parse(JSON.stringify(newData.connections || []))
    } else if (newData.nodes && newData.connections) {
      previousNodes = JSON.parse(JSON.stringify(newData.nodes))
      previousConnections = JSON.parse(JSON.stringify(newData.connections || []))
    }
  },
  { deep: true }
)

// Load diagram from library if diagramId is in query
async function loadDiagramFromLibrary(diagramId: string): Promise<void> {
  diagramStore.resetSessionEditCount()
  const diagram = await savedDiagramsStore.getDiagram(diagramId)
  if (diagram) {
    // Set active diagram ID
    savedDiagramsStore.setActiveDiagram(diagramId)

    // Clear undo/redo history when switching diagrams
    diagramStore.clearHistory()

    // Restore LLM results if diagram was saved with multiple model results
    const spec = diagram.spec as Record<string, unknown>
    const llmResults = spec?.llm_results as
      | { results?: Record<string, unknown>; selectedModel?: string }
      | undefined
    let specForLoad = spec
    if (llmResults?.results && typeof llmResults.results === 'object') {
      llmResultsStore.restoreFromSaved(
        llmResults as { results?: Record<string, LLMResult>; selectedModel?: string },
        diagram.diagram_type
      )
      specForLoad = { ...spec }
      delete (specForLoad as Record<string, unknown>).llm_results
    } else {
      llmResultsStore.clearCache()
    }

    // Emit so useDiagramAutoSave suppresses auto-save (avoids redundant save)
    eventBus.emit('diagram:loaded_from_library', {
      diagramId,
      diagramType: diagram.diagram_type,
    })
    const loaded = diagramStore.loadFromSpec(
      specForLoad,
      diagram.diagram_type as DiagramType
    )

    if (loaded) {
      uiStore.setSelectedChartType(
        Object.entries(diagramTypeMap).find(([_, v]) => v === diagram.diagram_type)?.[0] ||
          diagram.diagram_type
      )
    }
  }
}

onMounted(async () => {
  document.addEventListener('fullscreenchange', handleFullscreenChange)

  // Initialize panel coordinator so panel:open_requested (e.g. 瀑布流) is handled
  getPanelCoordinator()
  // Initialize inline recommendations coordinator (topic updates, pane click, etc.)
  inlineRecCoordinator.setup()

  // Inline recommendations: Tab triggers when user is editing a node (after double-click)
  eventBus.onWithOwner(
    'node_editor:tab_pressed',
    (data: { nodeId?: string }) => {
      const nodeId = data?.nodeId
      if (!nodeId) return
      const nodes = diagramStore.data?.nodes ?? []
      const node = nodes.find((n: { id?: string }) => n.id === nodeId) as
        | { id?: string; type?: string }
        | undefined
      if (!node || !isNodeEligibleForInlineRec(node)) return
      if (!inlineRecStore.isReady) return
      startRecommendations(nodeId)
    },
    'CanvasPage'
  )

  // Initialize node palette singleton and listen for open events (start session when no restore)
  const { startSession } = getNodePalette({
    language: isZh.value ? 'zh' : 'en',
    onError: (err) => notify.error(err),
  })
  eventBus.onWithOwner(
    'nodePalette:opened',
    (data: { hasRestoredSession?: boolean; wasPanelAlreadyOpen?: boolean }) => {
      if (!data.hasRestoredSession && diagramStore.data?.nodes?.length) {
        nextTick().then(() =>
          startSession({ keepSessionId: data.wasPanelAlreadyOpen ?? false })
        )
      }
    },
    'CanvasPage'
  )

  // Fetch diagrams to know current slot count
  await savedDiagramsStore.fetchDiagrams()

  // Priority 1: Load saved diagram by ID from library
  const diagramId = route.query.diagramId
  if (diagramId) {
    await loadDiagramFromLibrary(String(diagramId))
    return // Don't load default template if loading from library
  }

  // Priority 1b: Load imported diagram from JSON (landing page Import button)
  const importFlag = route.query.import
  if (importFlag === '1') {
    const importJson = sessionStorage.getItem(IMPORT_SPEC_KEY)
    if (importJson) {
      try {
        const spec = JSON.parse(importJson) as Record<string, unknown>
        sessionStorage.removeItem(IMPORT_SPEC_KEY)
        const diagramType = (spec.type as DiagramType) || null
        if (!diagramType || !VALID_DIAGRAM_TYPES.includes(diagramType)) {
          notify.error(
            isZh.value ? '导入失败，不支持的图示类型' : 'Import failed: unsupported diagram type'
          )
        } else {
          const llmResults = spec.llm_results as
            | { results?: Record<string, unknown>; selectedModel?: string }
            | undefined
          let specForLoad = spec
          if (llmResults?.results && typeof llmResults.results === 'object') {
            llmResultsStore.restoreFromSaved(
              llmResults as { results?: Record<string, LLMResult>; selectedModel?: string },
              diagramType
            )
            specForLoad = { ...spec }
            delete (specForLoad as Record<string, unknown>).llm_results
          } else {
            llmResultsStore.clearCache()
          }
          const loaded = diagramStore.loadFromSpec(specForLoad, diagramType)
          if (loaded) {
            const chineseName = diagramTypeToChineseMap[diagramType]
            if (chineseName) {
              uiStore.setSelectedChartType(chineseName)
            }
            router.replace({ path: '/canvas' })

            // Save imported diagram to user's library
            const topicText = diagramStore.getTopicNodeText()
            const importTitle =
              topicText ||
              diagramStore.effectiveTitle ||
              getDefaultDiagramName(diagramType, isZh.value)
            diagramStore.initTitle(importTitle)
            const getDiagramSpec = useDiagramSpecForSave()
            const specToSave = getDiagramSpec()
            if (specToSave && authStore.isAuthenticated) {
              const saveResult = await savedDiagramsStore.manualSaveDiagram(
                importTitle,
                diagramType,
                specToSave,
                isZh.value ? 'zh' : 'en',
                null
              )
              if (saveResult.success) {
                notify.success(
                  isZh.value ? '图示已导入并保存到图库' : 'Diagram imported and saved to library'
                )
              } else if (saveResult.needsSlotClear) {
                eventBus.emit('canvas:show_slot_full_modal', {})
              } else if (!saveResult.success) {
                notify.warning(
                  saveResult.error ||
                    (isZh.value ? '导入成功，但保存到图库失败' : 'Imported, but save to library failed')
                )
              }
            }
            return
          }
          notify.error(
            isZh.value ? '导入失败，图示数据无法加载' : 'Import failed: diagram could not be loaded'
          )
        }
      } catch (error) {
        console.error('Import load failed:', error)
        notify.error(isZh.value ? '导入失败，图示数据无效' : 'Import failed: invalid diagram data')
      }
    }
  }

  // Priority 2: Load new diagram by type from URL (survives page refresh)
  const typeFromUrl = route.query.type as DiagramType | undefined
  if (typeFromUrl && VALID_DIAGRAM_TYPES.includes(typeFromUrl)) {
    // Sync UI store with type from URL
    const chineseName = diagramTypeToChineseMap[typeFromUrl]
    if (chineseName) {
      uiStore.setSelectedChartType(chineseName)
    }
    diagramStore.setDiagramType(typeFromUrl)
    if (!diagramStore.data) {
      diagramStore.loadDefaultTemplate(typeFromUrl)
    }
    return
  }

  // Priority 3: Use UI store (backward compat, will be lost on refresh)
  if (diagramType.value) {
    diagramStore.setDiagramType(diagramType.value)
    // Load default template on mount if type is provided and no existing diagram
    if (!diagramStore.data) {
      // Load static default template (no AI generation)
      diagramStore.loadDefaultTemplate(diagramType.value)
    }
  }
  // If no type specified, canvas shows empty state
  // User should navigate back to select a diagram type
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', handleFullscreenChange)

  if (document.fullscreenElement) {
    document.exitFullscreen().catch(() => {})
  }

  diagramAutoSave.teardown()
  inlineRecCoordinator.teardown()
  eventBus.removeAllListenersForOwner('CanvasPage')

  // Clean up workshop connection when leaving canvas
  // Note: Workshop cleanup is handled by useWorkshop composable's onUnmounted
  // But we should also clear workshop code from CanvasTopBar if needed

  // Clean up state when leaving canvas - matches old JS behavior
  diagramStore.reset()
  savedDiagramsStore.clearActiveDiagram()
  useLLMResultsStore().reset()
  // Reset panels (nodePalette, property, mindmate) to avoid memory leaks from
  // canvas-specific data (suggestions, nodeData)
  usePanelsStore().reset()
  uiStore.setSelectedChartType('选择具体图示')
  uiStore.setFreeInputValue('')
  handToolActive.value = false
  isPresentationMode.value = false

  // Reset previous state tracking
  previousNodes = []
  previousConnections = []
})
</script>

<template>
  <div
    ref="canvasPageRef"
    class="canvas-page flex flex-col h-screen bg-gray-50 relative"
  >
    <!-- Top navigation bar (hidden in presentation mode) -->
    <CanvasTopBar
      v-if="!isPresentationMode"
      :auto-saved-status="autoSavedStatusText"
      :slot-full-and-new-diagram="isSlotsFullAndNewDiagram"
      :focus-question="conceptMapFocusQuestionDisplay"
      @save-requested="handleSaveKey"
    />

    <!-- Concept map standard mode: blur canvas until focus question is set -->
    <div
      v-if="showConceptMapFocusGate"
      class="absolute top-12 left-0 right-0 bottom-0 z-[90] flex items-center justify-center p-4 bg-slate-900/25 dark:bg-black/40 backdrop-blur-md"
      aria-hidden="false"
    >
      <ConceptMapFocusQuestionModal
        :is-authenticated="authStore.isAuthenticated"
        @confirm="handleConceptMapFocusConfirmed"
      />
    </div>

    <!-- Floating toolbar (only UI bar visible in presentation mode) -->
    <CanvasToolbar
      :is-presentation-mode="isPresentationMode"
      @exit-presentation="handleStartPresentation"
    />

    <!-- Main canvas area - full height, toolbars float over with glass effect -->
    <div class="flex-1 relative overflow-hidden flex flex-row min-h-0">
      <!-- Node Palette panel (瀑布流) - left 50%, inset to clear floating toolbars -->
      <Transition name="node-palette-slide">
        <div
          v-if="panelsStore.nodePalettePanel.isOpen"
          class="node-palette-panel-split shrink-0 flex flex-col bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-xl overflow-hidden ml-4 mr-2 self-stretch"
          :style="{
            width: '50%',
            minWidth: `${PANEL.NODE_PALETTE_MIN_WIDTH}px`,
            maxWidth: `${PANEL.NODE_PALETTE_MAX_WIDTH}px`,
            marginTop: `${PANEL_INSET.TOP}px`,
            marginBottom: `${PANEL_INSET.BOTTOM}px`,
            maxHeight: `calc(100vh - ${PANEL_INSET.VERTICAL_TOTAL}px)`,
          }"
        >
          <NodePalettePanel @close="panelsStore.closeNodePalette" />
        </div>
      </Transition>

      <!-- Diagram area - takes remaining space -->
      <div class="flex-1 min-w-0 flex flex-col relative">
        <DiagramCanvas
          v-if="diagramStore.data"
          class="w-full flex-1 min-h-0"
          :show-background="true"
          :show-minimap="false"
          :fit-view-on-init="true"
          :hand-tool-active="handToolActive"
          @node-double-click="handleNodeDoubleClick"
        />
      </div>

      <!-- MindMate floating panel (教学设计) - rounded card, inset to clear floating toolbars -->
      <Transition name="mindmate-slide">
        <div
          v-if="panelsStore.mindmatePanel.isOpen"
          class="mindmate-panel-float fixed z-50 flex flex-col bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-xl overflow-hidden"
          :style="{
            width: `${PANEL.MINDMATE_WIDTH}px`,
            top: `${PANEL_INSET.TOP}px`,
            right: '16px',
            height: `calc(100vh - ${PANEL_INSET.VERTICAL_TOTAL}px)`,
            minHeight: '400px',
            maxHeight: `calc(100vh - ${PANEL_INSET.VERTICAL_TOTAL}px)`,
          }"
        >
          <MindmatePanel
            mode="panel"
            class="flex-1 min-h-0 flex flex-col"
            @close="panelsStore.closeMindmate"
          />
        </div>
      </Transition>
    </div>

    <!-- Bottom controls: single floating glass card, adaptive width -->
    <div class="canvas-bottom-controls absolute bottom-4 left-0 right-0 z-20 flex justify-center px-2 sm:px-4">
      <div
        class="bottom-controls-card flex flex-col md:flex-row md:items-center gap-2 md:gap-3 rounded-xl shadow-lg p-1.5 md:p-2 border border-gray-200/80 dark:border-gray-600/80 bg-white/90 dark:bg-gray-800/90 backdrop-blur-md w-fit max-w-[95vw] min-w-0"
      >
        <div class="ai-selector-wrap flex flex-1 justify-center md:justify-center min-w-0 order-2 md:order-1">
          <AIModelSelector @model-change="handleModelChange" />
        </div>
        <ConceptMapLabelPicker
          v-if="diagramStore.type === 'concept_map'"
          class="label-picker-wrap order-3 shrink-0 min-w-0"
        />
        <InlineRecommendationsPicker
          v-else-if="inlineRecActiveNodeId"
          class="label-picker-wrap order-3 shrink-0 min-w-0"
        />
        <div
          v-if="showZoomControls"
          class="zoom-controls-wrap flex shrink-0 order-1 md:order-2"
        >
          <ZoomControls
            :zoom="canvasZoom"
            :is-presentation-mode="isPresentationMode"
            @zoom-change="handleZoomChange"
            @zoom-in="handleZoomIn"
            @zoom-out="handleZoomOut"
            @fit-to-screen="handleFitToScreen"
            @hand-tool-toggle="handleHandToolToggle"
            @start-presentation="handleStartPresentation"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Node Palette panel slide-in animation (from left) */
.node-palette-slide-enter-active,
.node-palette-slide-leave-active {
  transition: transform 0.3s ease;
}

.node-palette-slide-enter-from,
.node-palette-slide-leave-to {
  transform: translateX(-100%);
}

.node-palette-slide-enter-to,
.node-palette-slide-leave-from {
  transform: translateX(0);
}

/* MindMate panel slide-in animation */
.mindmate-slide-enter-active,
.mindmate-slide-leave-active {
  transition: transform 0.3s ease;
}

.mindmate-slide-enter-from,
.mindmate-slide-leave-to {
  transform: translateX(100%);
}

.mindmate-slide-enter-to,
.mindmate-slide-leave-from {
  transform: translateX(0);
}

/* Short viewport: compact bottom controls */
@media (max-height: 560px) {
  .ai-selector-wrap {
    justify-content: flex-start;
  }
}
</style>
