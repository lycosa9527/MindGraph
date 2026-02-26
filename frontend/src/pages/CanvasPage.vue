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
 * Auto-save functionality:
 * - Debounced auto-save on diagram changes (2 second delay)
 * - Auto-updates if diagram is already in library
 * - Auto-saves new diagrams if slots available
 * - Silently skips if slots full (user must manually save via File menu)
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { AIModelSelector, CanvasToolbar, CanvasTopBar, ZoomControls } from '@/components/canvas'
import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import {
  eventBus,
  getDefaultDiagramName,
  useEditorShortcuts,
  useLanguage,
  useNotifications,
  useWorkshop,
} from '@/composables'
import { ANIMATION } from '@/config/uiConfig'
import {
  useAuthStore,
  useDiagramStore,
  useLLMResultsStore,
  usePanelsStore,
  useSavedDiagramsStore,
  useUIStore,
} from '@/stores'
import type { DiagramType } from '@/types'

const route = useRoute()
const router = useRouter()
const diagramStore = useDiagramStore()
const uiStore = useUIStore()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()
const { isZh } = useLanguage()
const notify = useNotifications()

// Canvas zoom for ZoomControls sync (updated via view:zoom_changed)
const canvasZoom = ref<number | null>(null)

// Hand tool: when active, left-click drag pans instead of moving nodes
const handToolActive = ref(false)

// Presentation mode: browser fullscreen, only top bar + bottom controls visible
const isPresentationMode = ref(false)
const canvasPageRef = ref<HTMLElement | null>(null)

// Auto-save debounce timer
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null
const AUTO_SAVE_DELAY = 2000 // 2 seconds debounce

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

// Valid diagram types for URL validation
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
  eventBus.emit('diagram:add_node_requested', {})
}

function handleClearNodeTextKey() {
  if (isTypingInInput()) return
  const selected = [...diagramStore.selectedNodes]
  if (selected.length === 0) {
    notify.warning(isZh.value ? '请先选择要清空的节点' : 'Please select a node to clear')
    return
  }
  const protectedIds = ['topic', 'event', 'dimension-label', 'outer-boundary']
  let clearedCount = 0
  for (const nodeId of selected) {
    if (protectedIds.includes(nodeId)) continue
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    if (node && node.type !== 'topic' && node.type !== 'center' && node.type !== 'boundary') {
      if (diagramStore.updateNode(nodeId, { text: '' })) {
        clearedCount++
      }
    }
  }
  if (clearedCount > 0) {
    diagramStore.pushHistory(isZh.value ? '清空节点文字' : 'Clear node text')
    notify.success(isZh.value ? `已清空 ${clearedCount} 个节点` : `Cleared ${clearedCount} node(s)`)
  } else {
    notify.warning(isZh.value ? '无法清空主题或中心节点' : 'Cannot clear topic or center nodes')
  }
}

useEditorShortcuts({
  delete: handleDeleteKey,
  addNode: handleAddNodeKey,
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

/**
 * Generate default diagram name (simple, no timestamp)
 * Format: "新圆圈图" / "New Circle Map"
 */
function generateDefaultName(): string {
  return getDefaultDiagramName(diagramTypeForName.value, isZh.value)
}

/**
 * Get the diagram title for auto-save
 * Priority: topic node text > user-edited title > simple default name (no timestamp)
 */
function getDiagramTitle(): string {
  // effectiveTitle already prioritizes: user-edited title > topic > stored title
  // If we have a topic, use it; otherwise use simple default
  const topicText = diagramStore.getTopicNodeText()
  if (topicText) {
    return topicText
  }
  // Fallback to effectiveTitle (which may have user-edited title) or simple default
  return diagramStore.effectiveTitle || generateDefaultName()
}

/** Get diagram spec for saving (uses recalculated positions for bubble map) */
function getDiagramSpec(): Record<string, unknown> | null {
  return diagramStore.getSpecForSave()
}

/**
 * Perform auto-save of current diagram
 * Called after debounce delay when diagram changes
 */
async function performAutoSave(): Promise<void> {
  // Don't auto-save if not authenticated
  if (!authStore.isAuthenticated) return

  // Don't auto-save if no diagram data
  if (!diagramStore.type || !diagramStore.data) return

  const spec = getDiagramSpec()
  if (!spec) return

  const title = getDiagramTitle()

  try {
    const result = await savedDiagramsStore.autoSaveDiagram(
      title,
      diagramStore.type,
      spec,
      isZh.value ? 'zh' : 'en',
      null // TODO: Generate thumbnail
    )

    // Log result for debugging (can be removed in production)
    if (result.success) {
      console.log(`[CanvasPage] Auto-save ${result.action}: diagram ${result.diagramId}`)

      // Sync URL with diagramId when a new diagram is saved
      // This ensures the diagram persists on page refresh
      if (result.action === 'saved' && result.diagramId) {
        router.replace({
          path: '/canvas',
          query: { diagramId: result.diagramId },
        })
      }
    } else if (result.action === 'skipped') {
      // Silent skip when slots full - this is expected
      console.log('[CanvasPage] Auto-save skipped: no available slots')
    }
    // Don't show notifications for auto-save - it should be invisible to user
  } catch (error) {
    console.error('[CanvasPage] Auto-save error:', error)
  }
}

/**
 * Debounced auto-save trigger
 * Resets timer on each call, only executes after delay
 */
function triggerAutoSave(): void {
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
  }
  autoSaveTimer = setTimeout(performAutoSave, AUTO_SAVE_DELAY)
}

// Watch for diagram data changes to trigger auto-save and send granular updates
watch(
  () => diagramStore.data,
  (newData, oldData) => {
    // Only auto-save if we have data and it's changed
    if (newData && oldData) {
      triggerAutoSave()

      // Send granular updates to workshop if active
      if (workshopCode.value && newData.nodes && newData.connections) {
        const changedNodes = calculateDiff(
          previousNodes as Array<{ id: string }>,
          newData.nodes as Array<{ id: string }>
        )
        const changedConnections = calculateDiff(
          previousConnections as Array<{ id: string }>,
          (newData.connections || []) as Array<{ id: string }>
        )

        // Only send if there are changes
        if (changedNodes.length > 0 || changedConnections.length > 0) {
          sendUpdate(undefined, changedNodes, changedConnections)
        }

        // Update previous state
        previousNodes = JSON.parse(JSON.stringify(newData.nodes))
        previousConnections = JSON.parse(JSON.stringify(newData.connections || []))
      } else if (newData.nodes && newData.connections) {
        // Initialize previous state
        previousNodes = JSON.parse(JSON.stringify(newData.nodes))
        previousConnections = JSON.parse(JSON.stringify(newData.connections || []))
      }
    }
  },
  { deep: true }
)

// Load diagram from library if diagramId is in query
async function loadDiagramFromLibrary(diagramId: string): Promise<void> {
  const diagram = await savedDiagramsStore.getDiagram(diagramId)
  if (diagram) {
    // Set active diagram ID
    savedDiagramsStore.setActiveDiagram(diagramId)

    // Load the diagram into store
    const loaded = diagramStore.loadFromSpec(diagram.spec, diagram.diagram_type as DiagramType)

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

  // Fetch diagrams to know current slot count
  await savedDiagramsStore.fetchDiagrams()

  // Priority 1: Load saved diagram by ID from library
  const diagramId = route.query.diagramId
  if (diagramId) {
    await loadDiagramFromLibrary(String(diagramId))
    return // Don't load default template if loading from library
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

  // Clear auto-save timer
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
    autoSaveTimer = null
  }

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
    class="canvas-page flex flex-col h-screen bg-gray-50"
  >
    <!-- Top navigation bar (hidden in presentation mode) -->
    <CanvasTopBar v-if="!isPresentationMode" />

    <!-- Floating toolbar (only UI bar visible in presentation mode) -->
    <CanvasToolbar
      :is-presentation-mode="isPresentationMode"
      @exit-presentation="handleStartPresentation"
    />

    <!-- Main canvas area - extends behind toolbar; zoom fit excludes toolbar via FIT_PADDING -->
    <div class="flex-1 relative overflow-hidden">
      <!-- Vue Flow Canvas -->
      <DiagramCanvas
        v-if="diagramStore.data"
        class="w-full h-full"
        :show-background="true"
        :show-minimap="false"
        :fit-view-on-init="true"
        :hand-tool-active="handToolActive"
      />
    </div>

    <!-- Zoom controls -->
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

    <!-- AI model selector -->
    <AIModelSelector @model-change="handleModelChange" />
  </div>
</template>
