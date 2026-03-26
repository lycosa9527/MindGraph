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
import { computed, nextTick, onMounted, onUnmounted, provide, ref, watch } from 'vue'

import { useRoute, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import {
  AIModelSelector,
  CanvasToolbar,
  CanvasTopBar,
  ConceptMapFocusReviewPicker,
  ConceptMapLabelPicker,
  ConceptMapRootConceptPicker,
  InlineRecommendationsPicker,
  ZoomControls,
} from '@/components/canvas'
import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import { MindmatePanel, NodePalettePanel, RootConceptModal } from '@/components/panels'
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
  useSnapshotHistory,
  useWorkshop,
} from '@/composables'
import { INLINE_RECOMMENDATIONS_SUPPORTED_TYPES } from '@/composables/nodePalette/constants'
import { DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR } from '@/config/presentationHighlighter'
import { IMPORT_SPEC_KEY, SAVE } from '@/config'
import { ANIMATION, PANEL, PANEL_INSET } from '@/config/uiConfig'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { intlLocaleForUiCode } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'
import {
  type LLMResult,
  useAuthStore,
  useConceptMapFocusReviewStore,
  useConceptMapRelationshipStore,
  useConceptMapRootConceptReviewStore,
  useDiagramStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
  usePanelsStore,
  useUIStore,
} from '@/stores'
import { stripConceptMapFocusQuestionPrefix } from '@/stores/diagram/diagramDefaultLabels'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType, PresentationHighlightStroke } from '@/types'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'

const route = useRoute()
const router = useRouter()
const diagramStore = useDiagramStore()
const relationshipStore = useConceptMapRelationshipStore()
const uiStore = useUIStore()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()
const llmResultsStore = useLLMResultsStore()
const panelsStore = usePanelsStore()
const { promptLanguage, t, currentLanguage } = useLanguage()
const notify = useNotifications()

const snapshotHistory = useSnapshotHistory()

// Singletons must be created during setup (not in onMounted); they use useI18n / onUnmounted.
getPanelCoordinator()
const { startSession: startNodePaletteSession } = getNodePalette({
  onError: (err) => notify.error(err),
})
const { activeEntry: relationshipActiveEntry } = storeToRefs(relationshipStore)
const focusReviewStore = useConceptMapFocusReviewStore()
const rootConceptReviewStore = useConceptMapRootConceptReviewStore()
const inlineRecStore = useInlineRecommendationsStore()
const { activeNodeId: inlineRecActiveNodeId } = storeToRefs(inlineRecStore)

// Hide zoom/pan when concept map label picker or inline recommendations picker is showing
const showZoomControls = computed(() => {
  const rel = diagramStore.type === 'concept_map' && relationshipActiveEntry.value
  const rootPick =
    diagramStore.type === 'concept_map' &&
    rootConceptReviewStore.showPicker &&
    !relationshipActiveEntry.value
  const focusPick =
    diagramStore.type === 'concept_map' &&
    focusReviewStore.showPicker &&
    !relationshipActiveEntry.value &&
    !rootPick
  return !(rel || rootPick || focusPick || inlineRecActiveNodeId.value)
})

/** Topic/focus_question text after optional 「焦点问题:」 — used in top bar as 焦点问题: {body} */
const conceptMapFocusQuestionDisplay = computed((): string | null => {
  if (diagramStore.type !== 'concept_map' || !diagramStore.data) return null
  const topicNode = diagramStore.data.nodes.find((n) => n.id === 'topic' || n.type === 'topic')
  let raw = topicNode?.text?.trim()
  if (!raw) {
    const fq = diagramStore.data.focus_question
    if (typeof fq === 'string' && fq.trim()) raw = fq.trim()
  }
  if (!raw) return null
  const body = stripConceptMapFocusQuestionPrefix(raw)
  return body || null
})

const inlineRecCoordinator = useInlineRecommendationsCoordinator()
const { startRecommendations } = useInlineRecommendations()

function isNodeEligibleForInlineRec(node: { id?: string; type?: string }): boolean {
  const dt = diagramStore.type === 'mind_map' ? 'mindmap' : diagramStore.type
  if (!dt || !(INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(dt))
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
    return nid === 'dimension-label' || /^tree-cat-\d+$/.test(nid) || /^tree-leaf-/.test(nid)
  }
  if (dt === 'brace_map') {
    return nid === 'dimension-label' || node.type === 'brace' || nid.startsWith('brace-')
  }
  if (dt === 'circle_map') {
    return nid.startsWith('context-')
  }
  if (dt === 'bubble_map') {
    return nid.startsWith('bubble-')
  }
  if (dt === 'double_bubble_map') {
    return (
      nid.startsWith('similarity-') || nid.startsWith('left-diff-') || nid.startsWith('right-diff-')
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
const presentationTool = ref<'laser' | 'spotlight' | 'highlighter'>('laser')
const presentationHighlighterColor = ref(DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR)
const presentationHighlightStrokes = ref<PresentationHighlightStroke[]>([])
const canvasPageRef = ref<HTMLElement | null>(null)

const presentationHighlighterActive = computed(() => presentationTool.value === 'highlighter')

/** Laser dot, spotlight hole, and highlighter stroke width (Ctrl+/Ctrl- in presentation) */
const presentationPointerSizeScale = ref(1)
const PRESENTATION_POINTER_SCALE_MIN = 0.5
const PRESENTATION_POINTER_SCALE_MAX = 2.5
const PRESENTATION_POINTER_SCALE_STEP = 0.1

const SPOTLIGHT_INNER_RADIUS_PX = 150
const SPOTLIGHT_OUTER_RADIUS_PX = 195
const LASER_CURSOR_BASE_PX = 22

// Laser / spotlight: track pointer for dot and radial reveal
const laserX = ref(0)
const laserY = ref(0)

function handleLaserMouseMove(event: MouseEvent) {
  laserX.value = event.clientX
  laserY.value = event.clientY
}

const spotlightStyle = computed(() => {
  const s = presentationPointerSizeScale.value
  const inner = SPOTLIGHT_INNER_RADIUS_PX * s
  const outer = SPOTLIGHT_OUTER_RADIUS_PX * s
  return {
    background: `radial-gradient(circle at ${laserX.value}px ${laserY.value}px, transparent 0%, transparent ${inner}px, rgba(0,0,0,0.62) ${outer}px)`,
  }
})

const laserCursorStyle = computed(() => {
  const s = presentationPointerSizeScale.value
  const size = LASER_CURSOR_BASE_PX * s
  const half = size / 2
  return {
    transform: `translate(${laserX.value}px, ${laserY.value}px)`,
    width: `${size}px`,
    height: `${size}px`,
    marginLeft: `-${half}px`,
    marginTop: `-${half}px`,
    boxShadow: [
      `0 0 ${4 * s}px ${2 * s}px rgba(255, 255, 255, 0.9)`,
      `0 0 ${10 * s}px ${4 * s}px rgba(255, 60, 60, 1)`,
      `0 0 ${22 * s}px ${8 * s}px rgba(220, 20, 20, 0.85)`,
      `0 0 ${45 * s}px ${18 * s}px rgba(180, 0, 0, 0.55)`,
      `0 0 ${80 * s}px ${35 * s}px rgba(140, 0, 0, 0.25)`,
    ].join(', '),
  }
})

function handlePresentationPointerSizeKeydown(event: KeyboardEvent) {
  if (!isPresentationMode.value) return
  if (!event.ctrlKey && !event.metaKey) return
  if (isTypingInInput()) return

  const code = event.code
  const key = event.key
  const increase =
    key === '+' ||
    key === '=' ||
    code === 'Equal' ||
    code === 'NumpadAdd'
  const decrease =
    key === '-' ||
    key === '_' ||
    code === 'Minus' ||
    code === 'NumpadSubtract'
  if (!increase && !decrease) return

  event.preventDefault()
  const delta = increase ? PRESENTATION_POINTER_SCALE_STEP : -PRESENTATION_POINTER_SCALE_STEP
  presentationPointerSizeScale.value = Math.min(
    PRESENTATION_POINTER_SCALE_MAX,
    Math.max(PRESENTATION_POINTER_SCALE_MIN, presentationPointerSizeScale.value + delta),
  )
}

watch(isPresentationMode, (active) => {
  if (active) {
    window.addEventListener('mousemove', handleLaserMouseMove)
    window.addEventListener('keydown', handlePresentationPointerSizeKeydown, true)
    presentationTool.value = 'laser'
  } else {
    window.removeEventListener('mousemove', handleLaserMouseMove)
    window.removeEventListener('keydown', handlePresentationPointerSizeKeydown, true)
    presentationHighlightStrokes.value = []
    presentationTool.value = 'laser'
    presentationHighlighterColor.value = DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR
    presentationPointerSizeScale.value = 1
  }
})

// Auto-save: event-driven, config-based (useDiagramAutoSave)
const diagramAutoSave = useDiagramAutoSave()

// Tick counter for relative time reactivity (increments every RELATIVE_TIME_TICK_MS)
const relativeTimeTick = ref(0)
let relativeTimeTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  relativeTimeTimer = setInterval(() => {
    relativeTimeTick.value++
  }, SAVE.RELATIVE_TIME_TICK_MS)
})
onUnmounted(() => {
  if (relativeTimeTimer) {
    clearInterval(relativeTimeTimer)
    relativeTimeTimer = null
  }
})

function formatRelativeTime(date: Date): string {
  // Force reactivity via tick counter
  void relativeTimeTick.value
  const diffMs = Date.now() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 10) return t('editor.savedJustNow')
  if (diffSec < 60) return t('editor.savedSecondsAgo', { n: diffSec })
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return t('editor.savedMinutesAgo', { n: diffMin })
  const timeStr = date.toLocaleTimeString(intlLocaleForUiCode(currentLanguage.value as LocaleCode), {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return t('editor.autoSavedAt').replace('{time}', timeStr)
}

// Auto-save status text next to file name
const autoSavedStatusText = computed(() => {
  if (!authStore.isAuthenticated) return null
  if (savedDiagramsStore.isSlotsFullyUsed && !savedDiagramsStore.activeDiagramId) {
    return t('editor.slotsFull')
  }
  if (diagramAutoSave.isSaving.value) return t('editor.saving')
  const at = diagramAutoSave.lastSavedAt.value
  if (!at) {
    if (diagramAutoSave.isDirty.value) return t('editor.unsavedChanges')
    return null
  }
  if (diagramAutoSave.isDirty.value) return t('editor.unsavedChanges')
  return formatRelativeTime(at)
})

// When slots full + new diagram, clicking status should open slot management modal
const isSlotsFullAndNewDiagram = computed(
  () =>
    authStore.isAuthenticated &&
    savedDiagramsStore.isSlotsFullyUsed &&
    !savedDiagramsStore.activeDiagramId
)

// Diagram presentation mode (collaborative editing via shared code)
const workshopCode = ref<string | null>(null)
const currentDiagramId = computed(() => savedDiagramsStore.activeDiagramId)

// Track previous diagram state for granular updates
let previousNodes: Array<Record<string, unknown>> = []
let previousConnections: Array<Record<string, unknown>> = []
/** True while applying inbound WS merge — same store drives outbound watch; skip re-broadcast. */
const applyingRemoteCollabPatch = ref(false)

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
  sendNodeSelected,
  notifyNodeEditing,
  activeEditors,
  remoteSelectionsByUser,
  isDiagramOwner,
  watchCode: watchWorkshopCode,
} = useWorkshop(
  workshopCode,
  currentDiagramId,
  undefined, // onUpdate (full spec - backward compat, not used)
  (nodes, connections) => {
    // Granular update handler: merge incoming changes
    if (nodes || connections) {
      applyingRemoteCollabPatch.value = true
      try {
        diagramStore.mergeGranularUpdate(nodes, connections)
        diagramStore.clearRedoStack()
      } finally {
        nextTick(() => {
          applyingRemoteCollabPatch.value = false
        })
      }
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
  },
  (spec, _version) => {
    const t = (spec.type as DiagramType) || diagramType.value
    if (!t) return
    applyingRemoteCollabPatch.value = true
    try {
      diagramStore.loadFromSpec(spec, t)
      eventBus.emit('diagram:workshop_snapshot_applied', {})
    } finally {
      nextTick(() => {
        applyingRemoteCollabPatch.value = false
      })
    }
  }
)

// Start watching for presentation code changes
watchWorkshopCode()

watch(
  () => workshopCode.value,
  (code) => {
    diagramStore.setCollabSessionActive(Boolean(code))
    if (!code) {
      diagramStore.setCollabForeignLockedNodeIds([])
    }
  },
  { immediate: true }
)

watch(
  () => activeEditors.value,
  (editors) => {
    const uid = Number(authStore.user?.id)
    const foreign: string[] = []
    for (const [nid, ed] of editors) {
      if (ed.user_id !== uid) {
        foreign.push(nid)
      }
    }
    diagramStore.setCollabForeignLockedNodeIds(foreign)
  },
  { deep: true, immediate: true }
)

const collabLockedNodeIds = computed(() => {
  const uid = Number(authStore.user?.id)
  const out: string[] = []
  for (const [nid, ed] of activeEditors.value) {
    if (ed.user_id !== uid) {
      out.push(nid)
    }
  }
  return out
})

let lastRemoteSelectionKey = ''
watch(
  () => remoteSelectionsByUser.value,
  (next) => {
    nextTick(() => {
      const key = JSON.stringify([...next.entries()])
      if (key === lastRemoteSelectionKey) return
      lastRemoteSelectionKey = key
      document.querySelectorAll('.collab-remote-selected').forEach((el) => {
        el.classList.remove('collab-remote-selected')
        el.removeAttribute('data-collab-remote-user')
      })
      for (const [, sel] of next) {
        const el = document.querySelector(`#${CSS.escape(sel.nodeId)}`) as HTMLElement | null
        if (el) {
          el.classList.add('collab-remote-selected')
          el.setAttribute('data-collab-remote-user', sel.username)
        }
      }
    })
  },
  { deep: true }
)

let lastSentSelectionNodeId: string | null = null
watch(
  () => [...diagramStore.selectedNodes],
  (ids) => {
    if (!workshopCode.value) {
      return
    }
    const primary = ids.length > 0 ? ids[0] : null
    if (primary === lastSentSelectionNodeId) {
      return
    }
    if (lastSentSelectionNodeId && lastSentSelectionNodeId !== primary) {
      sendNodeSelected(lastSentSelectionNodeId, false)
    }
    if (primary) {
      sendNodeSelected(primary, true)
    }
    lastSentSelectionNodeId = primary
  },
  { deep: true }
)

provide('collabCanvas', {
  isNodeLockedByOther: (nodeId: string) => {
    const ed = activeEditors.value.get(nodeId)
    if (!ed) {
      return false
    }
    return ed.user_id !== Number(authStore.user?.id)
  },
  isDiagramOwner,
})

// Apply visual indicator to node (add CSS class and data attributes)
function applyNodeEditingIndicator(
  nodeId: string,
  editor: { color: string; emoji: string; username: string }
): void {
  nextTick(() => {
    // Vue Flow nodes use id attribute, not data-id
    const nodeElement = document.querySelector(`#${CSS.escape(nodeId)}`) as HTMLElement
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
    const nodeElement = document.querySelector(`#${CSS.escape(nodeId)}`) as HTMLElement
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

// Watch for presentation code changes from CanvasTopBar
// CanvasTopBar owns the modal; we sync the code here for useWorkshop
eventBus.onWithOwner(
  'workshop:code-changed',
  (data) => {
    if (data.code !== undefined) {
      workshopCode.value = data.code as string | null
    }
  },
  'CanvasPage'
)

eventBus.onWithOwner(
  'diagram:collab_delete_blocked',
  () => {
    notify.warning(t('notification.collabDeleteBlocked'))
  },
  'CanvasPage'
)

function applyJoinWorkshopFromQuery(): void {
  const raw = route.query.join_workshop
  if (!raw || typeof raw !== 'string') {
    return
  }
  const trimmed = raw.trim()
  if (!/^\d{3}-\d{3}$/.test(trimmed)) {
    return
  }
  workshopCode.value = trimmed
  eventBus.emit('workshop:code-changed', { code: trimmed })
  const nextQuery = { ...route.query } as Record<string, string | string[] | undefined>
  delete nextQuery.join_workshop
  router.replace({ query: nextQuery })
}

// Track node editing via eventBus
eventBus.onWithOwner(
  'node_editor:opening',
  (data) => {
    const nodeId = (data as { nodeId: string }).nodeId
    if (!nodeId || !workshopCode.value) {
      return
    }
    const ed = activeEditors.value.get(nodeId)
    if (ed && ed.user_id !== Number(authStore.user?.id)) {
      notify.warning(t('notification.canvasSomeoneEditingNode'))
      return
    }
    notifyNodeEditing(nodeId, true)
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
    notify.error(t('notification.fullscreenFailed'))
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

function nodeIdsDiffBetweenDiagrams(
  a: { nodes?: { id: string }[] } | null,
  b: { nodes?: { id: string }[] } | null
): Set<string> {
  const ids = new Set<string>()
  const nodesA = a?.nodes ?? []
  const nodesB = b?.nodes ?? []
  const mapB = new Map(nodesB.map((n) => [n.id, n]))
  for (const n of nodesA) {
    const o = mapB.get(n.id)
    if (!o || JSON.stringify(n) !== JSON.stringify(o)) {
      ids.add(n.id)
    }
  }
  for (const n of nodesB) {
    if (!nodesA.find((x) => x.id === n.id)) {
      ids.add(n.id)
    }
  }
  return ids
}

function handleUndoKey() {
  if (isTypingInInput()) return
  if (!diagramStore.canUndo) {
    return
  }
  if (workshopCode.value) {
    const prevEntry = diagramStore.history[diagramStore.historyIndex - 1]
    const cur = diagramStore.data
    if (prevEntry?.data && cur) {
      const changed = nodeIdsDiffBetweenDiagrams(
        cur,
        prevEntry.data as { nodes?: { id: string }[] }
      )
      for (const nid of changed) {
        const ed = activeEditors.value.get(nid)
        if (ed && ed.user_id !== Number(authStore.user?.id)) {
          notify.warning(t('notification.collabUndoBlocked'))
          return
        }
      }
    }
  }
  diagramStore.undo()
}

function handleRedoKey() {
  if (isTypingInInput()) return
  if (!diagramStore.canRedo) {
    return
  }
  if (workshopCode.value) {
    const nextEntry = diagramStore.history[diagramStore.historyIndex + 1]
    const cur = diagramStore.data
    if (nextEntry?.data && cur) {
      const changed = nodeIdsDiffBetweenDiagrams(
        cur,
        nextEntry.data as { nodes?: { id: string }[] }
      )
      for (const nid of changed) {
        const ed = activeEditors.value.get(nid)
        if (ed && ed.user_id !== Number(authStore.user?.id)) {
          notify.warning(t('notification.collabRedoBlocked'))
          return
        }
      }
    }
  }
  diagramStore.redo()
}

function handleClearNodeTextKey() {
  if (isTypingInInput()) return
  if (relationshipActiveEntry.value) return
  const selected = [...diagramStore.selectedNodes]
  if (selected.length === 0) {
    notify.warning(t('notification.selectNodeToClear'))
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
      isLearningSheet ? t('notification.historyEmptyLearning') : t('notification.historyClearNodes')
    )
    notify.success(
      isLearningSheet
        ? t('notification.canvasClearNodesLearning', { count: clearedCount })
        : t('notification.canvasClearNodes', { count: clearedCount })
    )
    // Save immediately when emptying nodes (learning sheet answers) so state persists
    if (isLearningSheet) {
      diagramAutoSave.performSave()
    }
  } else {
    notify.warning(t('notification.cannotClearTopicOrCenter'))
  }
}

async function handleSaveKey() {
  if (!authStore.isAuthenticated) {
    notify.warning(t('editor.saveNeedsLogin'))
    return
  }
  const result = await diagramAutoSave.flush()
  if (result.saved) {
    notify.success(t('editor.savedSuccess'))
  } else if (result.reason === 'skipped_slots_full') {
    eventBus.emit('canvas:show_slot_full_modal', {} as never)
  }
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
eventBus.onWithOwner(
  'diagram:type_changed',
  () => panelsStore.clearNodePaletteState(),
  'CanvasPage'
)

// Concept map Tab mode (focus + root pickers): dismiss like inline rec — pane click or selection away
eventBus.onWithOwner(
  'canvas:pane_clicked',
  () => {
    if (diagramStore.type !== 'concept_map') return
    focusReviewStore.clear()
    rootConceptReviewStore.clear()
  },
  'CanvasPage'
)
eventBus.onWithOwner(
  'state:selection_changed',
  ({ selectedNodes }: { selectedNodes: string[] }) => {
    if (diagramStore.type !== 'concept_map') return
    const nodes = selectedNodes ?? []
    const rootId = getTopicRootConceptTargetId(diagramStore.data?.connections)

    const focusActive = focusReviewStore.validating || focusReviewStore.reviewWaveComplete
    if (focusActive && !nodes.includes('topic')) {
      focusReviewStore.clear()
    }

    const rootActive =
      rootConceptReviewStore.streamPhase !== 'idle' ||
      rootConceptReviewStore.reviewWaveComplete ||
      rootConceptReviewStore.loadingMoreSuggestions
    if (rootActive && (!rootId || !nodes.includes(rootId))) {
      rootConceptReviewStore.clear()
    }
  },
  'CanvasPage'
)

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
  () => {
    const q = route.query
    const id = q.diagramId ?? q.diagram_id
    return typeof id === 'string' ? id : Array.isArray(id) ? id[0] : undefined
  },
  async (newId, oldId) => {
    if (newId && typeof newId === 'string' && newId !== oldId) {
      await loadDiagramFromLibrary(newId)
    } else if (!newId && oldId) {
      // Route dropped the diagramId — clear stale snapshot badges
      snapshotHistory.clearSnapshots()
    }
  }
)

// Watch for diagram data changes to send granular updates to presentation mode
// Auto-save: handled internally by useDiagramAutoSave (computed fingerprint + watch)
watch(
  () => diagramStore.data,
  (newData) => {
    if (!newData) return

    // Send granular updates to workshop if active (any change including position)
    if (workshopCode.value && newData.nodes && newData.connections) {
      if (applyingRemoteCollabPatch.value) {
        previousNodes = JSON.parse(JSON.stringify(newData.nodes))
        previousConnections = JSON.parse(JSON.stringify(newData.connections || []))
        return
      }
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
    const loaded = diagramStore.loadFromSpec(specForLoad, diagram.diagram_type as DiagramType)

    if (loaded) {
      uiStore.setSelectedChartType(
        Object.entries(diagramTypeMap).find(([_, v]) => v === diagram.diagram_type)?.[0] ||
          diagram.diagram_type
      )
    }
    snapshotHistory.setActiveVersion(null)
    await snapshotHistory.loadSnapshots(diagramId)
  }
}

async function handleSnapshotRecall(versionNumber: number): Promise<void> {
  const diagramId = savedDiagramsStore.activeDiagramId
  const diagramType = diagramStore.type
  if (!diagramId || !diagramType) return

  await diagramAutoSave.flush()

  const spec = await snapshotHistory.recallSnapshot(diagramId, versionNumber)
  if (!spec) {
    notify.error(t('canvas.topBar.snapshotRecallFailed'))
    return
  }

  diagramStore.pushHistory(t('canvas.topBar.snapshotRecallHistory', { n: versionNumber }))
  llmResultsStore.clearCache()
  eventBus.emit('diagram:loaded_from_library', { diagramId, diagramType })
  diagramStore.loadFromSpec(spec, diagramType)
  snapshotHistory.setActiveVersion(versionNumber)
}

async function handleSnapshotDelete(versionNumber: number): Promise<void> {
  const diagramId = savedDiagramsStore.activeDiagramId
  if (!diagramId) return

  const deleted = await snapshotHistory.deleteSnapshot(diagramId, versionNumber)
  if (deleted) {
    notify.success(t('canvas.topBar.snapshotDeleted', { n: versionNumber }))
  } else {
    notify.error(t('canvas.topBar.snapshotDeleteFailed'))
  }
}

onMounted(async () => {
  await ensureFontsForLanguageCode(uiStore.promptLanguage)

  document.addEventListener('fullscreenchange', handleFullscreenChange)

  // Initialize inline recommendations coordinator (topic updates, pane click, etc.)
  inlineRecCoordinator.setup()

  // Snapshot: capture current diagram spec to DB
  eventBus.onWithOwner(
    'snapshot:requested',
    async () => {
      const diagramId = savedDiagramsStore.activeDiagramId
      if (!diagramId) return
      const spec = diagramStore.getSpecForSave()
      if (!spec) return
      const result = await snapshotHistory.takeSnapshot(diagramId, spec)
      if (result) {
        notify.success(t('canvas.toolbar.snapshotTaken', { n: result.version_number }))
      } else {
        notify.error(t('canvas.toolbar.snapshotFailed'))
      }
    },
    'CanvasPage'
  )

  // Tab while editing: concept map topic → focus validation; other diagrams → inline recommendations
  eventBus.onWithOwner(
    'node_editor:tab_pressed',
    (data: { nodeId?: string; draftText?: string }) => {
      const nodeId = data?.nodeId
      if (!nodeId) return

      if (diagramStore.type === 'concept_map' && nodeId === 'topic') {
        const draft = typeof data.draftText === 'string' ? data.draftText.trim() : ''
        if (draft) {
          eventBus.emit('node:text_updated', { nodeId: 'topic', text: draft })
        }
        void focusReviewStore.runFocusReviewManual()
        return
      }

      if (diagramStore.type === 'concept_map') {
        const rootTid = getTopicRootConceptTargetId(diagramStore.data?.connections)
        if (rootTid && nodeId === rootTid) {
          const draft = typeof data.draftText === 'string' ? data.draftText.trim() : ''
          if (draft) {
            eventBus.emit('node:text_updated', { nodeId: rootTid, text: draft })
          }
          if (!authStore.isAuthenticated) {
            notify.warning(t('notification.signInToUse'))
            return
          }
          void rootConceptReviewStore.runRootConceptManual()
          return
        }
      }

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

  // Node palette: listen for open events (singleton created at setup top)
  eventBus.onWithOwner(
    'nodePalette:opened',
    (data: { hasRestoredSession?: boolean; wasPanelAlreadyOpen?: boolean }) => {
      if (!data.hasRestoredSession && diagramStore.data?.nodes?.length) {
        nextTick().then(() =>
          startNodePaletteSession({ keepSessionId: data.wasPanelAlreadyOpen ?? false })
        )
      }
    },
    'CanvasPage'
  )

  // Fetch diagrams to know current slot count
  await savedDiagramsStore.fetchDiagrams()

  // Priority 1: Load saved diagram by ID from library (accept diagramId or legacy diagram_id)
  const diagramIdRaw = route.query.diagramId ?? route.query.diagram_id
  const diagramId =
    typeof diagramIdRaw === 'string'
      ? diagramIdRaw
      : Array.isArray(diagramIdRaw)
        ? diagramIdRaw[0]
        : undefined
  if (diagramId) {
    await loadDiagramFromLibrary(String(diagramId))
    applyJoinWorkshopFromQuery()
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
          notify.error(t('notification.importUnsupportedType'))
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
              getDefaultDiagramName(diagramType, currentLanguage.value)
            diagramStore.initTitle(importTitle)
            const getDiagramSpec = useDiagramSpecForSave()
            const specToSave = getDiagramSpec()
            if (specToSave && authStore.isAuthenticated) {
              const saveResult = await savedDiagramsStore.manualSaveDiagram(
                importTitle,
                diagramType,
                specToSave,
                promptLanguage.value,
                null
              )
              if (saveResult.success) {
                notify.success(t('notification.importSuccess'))
              } else if (saveResult.needsSlotClear) {
                eventBus.emit('canvas:show_slot_full_modal', {})
              } else if (!saveResult.success) {
                notify.warning(saveResult.error || t('notification.importSavePartial'))
              }
            }
            return
          }
          notify.error(t('notification.importLoadFailed'))
        }
      } catch (error) {
        console.error('Import load failed:', error)
        notify.error(t('notification.importInvalidData'))
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
  window.removeEventListener('mousemove', handleLaserMouseMove)
  window.removeEventListener('keydown', handlePresentationPointerSizeKeydown, true)

  if (document.fullscreenElement) {
    document.exitFullscreen().catch(() => {})
  }

  diagramAutoSave.flush()
  diagramAutoSave.teardown()
  inlineRecCoordinator.teardown()
  eventBus.removeAllListenersForOwner('CanvasPage')

  // Presentation-mode WebSocket cleanup is handled in useWorkshop onUnmounted

  // Clean up state when leaving canvas - matches old JS behavior
  diagramStore.reset()
  savedDiagramsStore.clearActiveDiagram()
  snapshotHistory.clearSnapshots()
  useLLMResultsStore().reset()
  // Reset panels (nodePalette, property, mindmate) to avoid memory leaks from
  // canvas-specific data (suggestions, nodeData)
  usePanelsStore().reset()
  uiStore.setSelectedChartType('选择具体图示')
  uiStore.setFreeInputValue('')
  handToolActive.value = false
  isPresentationMode.value = false
  presentationHighlightStrokes.value = []
  presentationTool.value = 'laser'
  presentationHighlighterColor.value = DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR
  presentationPointerSizeScale.value = 1

  // Reset previous state tracking
  previousNodes = []
  previousConnections = []
})
</script>

<template>
  <div
    ref="canvasPageRef"
    class="canvas-page flex flex-col h-screen bg-gray-50 relative"
    :class="{
      'presentation-active': isPresentationMode,
      'presentation-highlighter-mode':
        isPresentationMode && presentationHighlighterActive,
    }"
  >
    <!-- Laser pointer cursor (presentation mode, laser tool) -->
    <Transition name="laser-fade">
      <div
        v-if="isPresentationMode && presentationTool === 'laser'"
        class="laser-cursor"
        :style="laserCursorStyle"
        aria-hidden="true"
      />
    </Transition>

    <!-- Spotlight overlay: dark vignette with circular reveal (spotlight tool) -->
    <Transition name="spotlight-fade">
      <div
        v-if="isPresentationMode && presentationTool === 'spotlight'"
        class="spotlight-overlay"
        :style="spotlightStyle"
        aria-hidden="true"
      />
    </Transition>

    <!-- Top navigation bar (hidden in presentation mode) -->
    <CanvasTopBar
      v-if="!isPresentationMode"
      :auto-saved-status="autoSavedStatusText"
      :slot-full-and-new-diagram="isSlotsFullAndNewDiagram"
      :is-dirty="diagramAutoSave.isDirty.value"
      :is-saving="diagramAutoSave.isSaving.value"
      :focus-question="conceptMapFocusQuestionDisplay"
      :snapshots="snapshotHistory.snapshots.value"
      :active-snapshot-version="snapshotHistory.activeSnapshotVersion.value"
      @save-requested="handleSaveKey"
      @snapshot-recall="handleSnapshotRecall"
      @snapshot-delete="handleSnapshotDelete"
    />

    <!-- Collaboration strip when fullscreen presentation hides the top bar -->
    <div
      v-if="isPresentationMode && workshopCode"
      class="fixed top-0 left-0 right-0 z-40 flex items-center justify-center gap-2 px-3 py-1.5 text-xs text-white bg-slate-800/90 backdrop-blur-sm border-b border-slate-600/60 pointer-events-none"
      role="status"
    >
      <span>{{ t('canvasPage.collaborationFooter') }}</span>
      <span class="opacity-60">·</span>
      <span class="font-mono">{{ workshopCode }}</span>
    </div>

    <!-- Floating toolbar (only UI bar visible in presentation mode) -->
    <CanvasToolbar
      :is-presentation-mode="isPresentationMode"
      @exitPresentation="handleStartPresentation"
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
          <RootConceptModal
            v-if="diagramStore.type === 'concept_map'"
            @close="panelsStore.closeNodePalette"
          />
          <NodePalettePanel
            v-else
            @close="panelsStore.closeNodePalette"
          />
        </div>
      </Transition>

      <!-- Diagram area - takes remaining space -->
      <div class="flex-1 min-w-0 flex flex-col relative">
        <DiagramCanvas
          v-if="diagramStore.data"
          v-model:presentation-highlight-strokes="presentationHighlightStrokes"
          v-model:presentation-tool="presentationTool"
          v-model:presentation-highlighter-color="presentationHighlighterColor"
          class="w-full flex-1 min-h-0"
          :show-background="true"
          :show-minimap="false"
          :fit-view-on-init="true"
          :hand-tool-active="handToolActive"
          :collab-locked-node-ids="collabLockedNodeIds"
          :presentation-mode="isPresentationMode"
          :presentation-pointer-size-scale="presentationPointerSizeScale"
          @node-double-click="handleNodeDoubleClick"
          @clear-presentation-highlighter="presentationHighlightStrokes = []"
          @exit-presentation="handleStartPresentation"
          @fit-presentation-view="handleFitToScreen"
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
    <div
      class="canvas-bottom-controls absolute bottom-4 left-0 right-0 z-20 flex justify-center px-2 sm:px-4"
    >
      <div
        class="bottom-controls-card flex flex-col md:flex-row md:items-center gap-2 md:gap-3 rounded-xl shadow-lg p-1.5 md:p-2 border border-gray-200/80 dark:border-gray-600/80 bg-white/90 dark:bg-gray-800/90 backdrop-blur-md w-fit max-w-[95vw] min-w-0"
      >
        <!-- shrink-0: AI block + focus picker width follows content (no flex-1 stretch) -->
        <div
          class="ai-selector-wrap flex shrink-0 justify-center md:justify-center min-w-0 order-2 md:order-1"
        >
          <AIModelSelector @model-change="handleModelChange" />
        </div>
        <ConceptMapLabelPicker
          v-if="diagramStore.type === 'concept_map' && relationshipActiveEntry"
          class="label-picker-wrap order-3 flex-1 min-w-0"
        />
        <ConceptMapRootConceptPicker
          v-else-if="
            diagramStore.type === 'concept_map' &&
            rootConceptReviewStore.showPicker &&
            !relationshipActiveEntry
          "
          class="label-picker-wrap order-3 shrink-0 w-fit max-w-[min(95vw,640px)] min-w-0"
        />
        <ConceptMapFocusReviewPicker
          v-else-if="diagramStore.type === 'concept_map' && focusReviewStore.showPicker"
          class="label-picker-wrap order-3 shrink-0 w-fit max-w-[min(95vw,640px)] min-w-0"
        />
        <InlineRecommendationsPicker
          v-else-if="inlineRecActiveNodeId"
          class="label-picker-wrap order-3 flex-1 min-w-0"
        />
        <div
          v-if="showZoomControls"
          class="zoom-controls-wrap flex shrink-0 order-1 md:order-2"
        >
          <ZoomControls
            :zoom="canvasZoom"
            :is-presentation-mode="isPresentationMode"
            @zoomChange="handleZoomChange"
            @zoomIn="handleZoomIn"
            @zoomOut="handleZoomOut"
            @fitToScreen="handleFitToScreen"
            @handToolToggle="handleHandToolToggle"
            @startPresentation="handleStartPresentation"
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

/* Hide the native cursor when presentation mode is active */
.presentation-active,
.presentation-active * {
  cursor: none !important;
}

/* Highlighter tool: brush-style cursor (overrides cursor: none above) */
.presentation-active.presentation-highlighter-mode,
.presentation-active.presentation-highlighter-mode * {
  cursor:
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Cpath d='M5 27 L11 8 L17 10 L13 29 Z' fill='%23fbbf24' stroke='%23b45309' stroke-width='1' stroke-linejoin='round'/%3E%3Cpath d='M11 8 L21 12 L17 26 L9 22 Z' fill='%23fde68a' opacity='0.95'/%3E%3Cpath d='M7 26 L9 18 L12 19 L10 27 Z' fill='%23f59e0b' opacity='0.55'/%3E%3C/svg%3E")
      10 26,
    crosshair !important;
}

/* Laser pointer dot — size/glow via inline style (presentationPointerSizeScale) */
.laser-cursor {
  position: fixed;
  top: 0;
  left: 0;
  border-radius: 50%;
  pointer-events: none;
  z-index: 99999;
  background: radial-gradient(circle at 40% 35%, #ff8080 0%, #ff1a1a 45%, #cc0000 70%, transparent 100%);
}

/* Subtle entrance / exit fade */
.laser-fade-enter-active,
.laser-fade-leave-active {
  transition: opacity 0.25s ease;
}

.laser-fade-enter-from,
.laser-fade-leave-to {
  opacity: 0;
}

/* Spotlight overlay: covers entire viewport, radial hole follows mouse */
.spotlight-overlay {
  position: fixed;
  inset: 0;
  z-index: 99998;
  pointer-events: none;
  /* background is set via inline :style (dynamic gradient position) */
}

/* Soft fade so the overlay doesn't pop in harshly */
.spotlight-fade-enter-active,
.spotlight-fade-leave-active {
  transition: opacity 0.3s ease;
}

.spotlight-fade-enter-from,
.spotlight-fade-leave-to {
  opacity: 0;
}
</style>
