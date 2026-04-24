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
import { useRoute, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import {
  AIModelSelector,
  CanvasChrome,
  CanvasTopBar,
  ConceptMapFocusReviewPicker,
  ConceptMapLabelPicker,
  ConceptMapRootConceptPicker,
  InlineRecommendationsPicker,
  PresentationSideToolbar,
  PresentationTimerOverlay,
  ZoomControls,
} from '@/components/canvas'
import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import { MindmatePanel, NodePalettePanel, RootConceptModal } from '@/components/panels'
import {
  eventBus,
  getDefaultDiagramName,
  getNodePalette,
  getPanelCoordinator,
  useDiagramSpecForSave,
  useEventBus,
  useInlineRecommendations,
  useInlineRecommendationsCoordinator,
  useLanguage,
  useNotifications,
  useSnapshotHistory,
} from '@/composables'
import { useDiagramAutoSave } from '@/composables/editor/useDiagramAutoSave'
import {
  VALID_DIAGRAM_TYPES,
  diagramTypeMap,
  diagramTypeToChineseMap,
} from '@/composables/canvasPage/diagramTypeMaps'
import { isNodeEligibleForInlineRec } from '@/composables/canvasPage/inlineRecEligibility'
import { registerCanvasPageDiagramEventBus } from '@/composables/canvasPage/registerCanvasPageDiagramEventBus'
import { useCanvasPageEditorShortcuts } from '@/composables/canvasPage/useCanvasPageEditorShortcuts'
import { useCanvasPageLibrarySnapshots } from '@/composables/canvasPage/useCanvasPageLibrarySnapshots'
import { useCanvasPagePresentation } from '@/composables/canvasPage/useCanvasPagePresentation'
import { useCanvasPageWorkshopCollab } from '@/composables/canvasPage/useCanvasPageWorkshopCollab'
import {
  diagramSpecLikelyNeedsMarkdownPipeline,
  loadDiagramMarkdownPipeline,
} from '@/composables/core/diagramMarkdownPipeline'
import { IMPORT_SPEC_KEY, SAVE } from '@/config'
import { FIT_PADDING, PANEL, PANEL_INSET } from '@/config/uiConfig'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { intlLocaleForUiCode } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'
import { useConceptMapFocusReviewStore } from '@/stores/conceptMapFocusReview'
import {
  type LLMResult,
  useAuthStore,
  useConceptMapRelationshipStore,
  useConceptMapRootConceptReviewStore,
  useDiagramStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
  usePanelsStore,
  useUIStore,
} from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
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

const {
  canvasPageRef,
  canvasZoom,
  handToolActive,
  presentationRailOpen,
  presentationTool,
  presentationHighlighterColor,
  presentationHighlightStrokes,
  timerTotalSeconds,
  timerRemainingSeconds,
  timerRunning,
  onTimerToggleRun,
  onTimerReset,
  onTimerPresetMinutes,
  onTimerExit,
  onTimerSetMinutes,
  laserCursorStyle,
  spotlightStyle,
  handleZoomChange,
  handleZoomIn,
  handleZoomOut,
  handleFitToScreen,
  handleHandToolToggle,
  handleStartPresentation,
  handleModelChange,
  resetPresentationStateOnLeave,
} = useCanvasPagePresentation()

/** Presentation rail virtual keyboard toggle (mirrors toolbar keyboard state). */
const virtualKeyboardOpen = ref(false)

const presentationShortcutBus = useEventBus('CanvasPagePresentationShortcuts')
presentationShortcutBus.on('presentation:toggle_virtual_keyboard_requested', () => {
  virtualKeyboardOpen.value = !virtualKeyboardOpen.value
})

const {
  workshopCode,
  activeEditors,
  collabLockedNodeIds,
  applyJoinWorkshopFromQuery,
  resetPreviousDiagramTracking,
} = useCanvasPageWorkshopCollab()

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

/** MindMate `right` offset: shift left when presentation rail is open so it does not cover the rail. */
const mindMatePanelRight = computed(() => {
  const base = PANEL.MINDMATE_RIGHT_OFFSET_PX
  if (presentationRailOpen.value && presentationTool.value !== 'timer') {
    return `${base + FIT_PADDING.PRESENTATION_SIDE_TOOLBAR_RIGHT_PX}px`
  }
  return `${base}px`
})

const inlineRecCoordinator = useInlineRecommendationsCoordinator()
const { startRecommendations } = useInlineRecommendations()

function handleNodeDoubleClick(_node: { id?: string; type?: string }): void {
  // Double-click only enters edit mode. Inline recommendations are triggered by Tab
  // when user is editing a node (see node_editor:tab_pressed listener).
}

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
  const timeStr = date.toLocaleTimeString(
    intlLocaleForUiCode(currentLanguage.value as LocaleCode),
    {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }
  )
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

// Get diagram type from UI store (set before navigation)
const chartType = computed(() => uiStore.selectedChartType)

const diagramType = computed<DiagramType | null>(() => {
  if (!chartType.value) return null
  return diagramTypeMap[chartType.value] || null
})

const { loadDiagramFromLibrary, handleSnapshotRecall, handleSnapshotDelete } =
  useCanvasPageLibrarySnapshots({ diagramAutoSave, snapshotHistory })

registerCanvasPageDiagramEventBus({ canvasZoom })

/** MindMate panel and presentation rail cannot both be active: opening one closes the other. */
watch(
  () => panelsStore.mindmatePanel.isOpen,
  (open) => {
    if (open && presentationRailOpen.value) {
      presentationRailOpen.value = false
      handToolActive.value = false
    }
  },
  { flush: 'sync' }
)

watch(
  () => presentationRailOpen.value,
  (open) => {
    if (open && panelsStore.mindmatePanel.isOpen) {
      panelsStore.closeMindmate()
    }
  },
  { flush: 'sync' }
)

const { handleSaveKey } = useCanvasPageEditorShortcuts({
  workshopCode,
  activeEditors,
  relationshipActiveEntry,
  diagramAutoSave,
})

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

onMounted(async () => {
  await ensureFontsForLanguageCode(uiStore.promptLanguage)

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
      if (!node || !isNodeEligibleForInlineRec(diagramStore.type, node, diagramStore.data?.connections))
        return
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

  // Priority 1b: Load imported diagram from `.mg` (landing page Import button)
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
          if (diagramSpecLikelyNeedsMarkdownPipeline(specForLoad)) {
            await loadDiagramMarkdownPipeline({ bumpLayout: false })
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
    } else {
      notify.error(t('canvas.import.invalidFile'))
      const restQuery = { ...route.query }
      delete restQuery.import
      await router.replace({ path: route.path, query: restQuery })
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
  diagramAutoSave.flush()
  diagramAutoSave.teardown()
  inlineRecCoordinator.teardown()
  eventBus.removeAllListenersForOwner('CanvasPage')

  // Clean up state when leaving canvas - matches old JS behavior
  diagramStore.reset()
  savedDiagramsStore.clearActiveDiagram()
  snapshotHistory.clearSnapshots()
  useLLMResultsStore().reset()
  usePanelsStore().reset()
  uiStore.setSelectedChartType('选择具体图示')
  uiStore.setFreeInputValue('')
  resetPresentationStateOnLeave()
  resetPreviousDiagramTracking()
})
</script>

<template>
  <div
    ref="canvasPageRef"
    class="canvas-page flex flex-col h-screen bg-gray-50 relative"
    :class="{
      'presentation-active': presentationRailOpen,
      'presentation-highlighter-mode': presentationRailOpen && presentationTool === 'highlighter',
      'presentation-pen-mode': presentationRailOpen && presentationTool === 'pen',
      'presentation-timer-mode': presentationRailOpen && presentationTool === 'timer',
    }"
  >
    <!-- Laser pointer cursor (presentation mode, laser tool) -->
    <Transition name="laser-fade">
      <div
        v-if="presentationRailOpen && presentationTool === 'laser'"
        class="laser-cursor"
        :style="laserCursorStyle"
        aria-hidden="true"
      />
    </Transition>

    <!-- Spotlight overlay: dark vignette with circular reveal (spotlight tool) -->
    <Transition name="spotlight-fade">
      <div
        v-if="presentationRailOpen && presentationTool === 'spotlight'"
        class="spotlight-overlay"
        :style="spotlightStyle"
        aria-hidden="true"
      />
    </Transition>

    <!-- Presentation timer: fullscreen dim + large countdown -->
    <PresentationTimerOverlay
      v-if="presentationRailOpen && presentationTool === 'timer'"
      :remaining-seconds="timerRemainingSeconds"
      :total-seconds="timerTotalSeconds"
      :running="timerRunning"
      @toggle-run="onTimerToggleRun"
      @reset="onTimerReset"
      @presetMinutes="onTimerPresetMinutes"
      @setMinutes="onTimerSetMinutes"
      @exit="onTimerExit"
    />

    <!-- Presentation tools: vertical rail (right); hidden during timer so overlay is unobstructed -->
    <PresentationSideToolbar
      v-if="presentationRailOpen && presentationTool !== 'timer'"
      :active-tool="presentationTool"
      :virtual-keyboard-open="virtualKeyboardOpen"
      @selectTool="presentationTool = $event"
      @clearHighlighter="presentationHighlightStrokes = []"
      @fit="handleFitToScreen"
      @exit="handleStartPresentation"
      @toggleVirtualKeyboard="virtualKeyboardOpen = !virtualKeyboardOpen"
    />

    <CanvasChrome>
      <CanvasTopBar
        :auto-saved-status="autoSavedStatusText"
        :slot-full-and-new-diagram="isSlotsFullAndNewDiagram"
        :is-dirty="diagramAutoSave.isDirty.value"
        :is-saving="diagramAutoSave.isSaving.value"
        :snapshots="snapshotHistory.snapshots.value"
        :active-snapshot-version="snapshotHistory.activeSnapshotVersion.value"
        @save-requested="handleSaveKey"
        @snapshot-recall="handleSnapshotRecall"
        @snapshot-delete="handleSnapshotDelete"
      />
    </CanvasChrome>

    <!-- Collaboration strip when workshop session is active -->
    <div
      v-if="workshopCode"
      class="fixed top-0 left-0 right-0 z-40 flex items-center justify-center gap-2 px-3 py-1.5 text-xs text-white bg-slate-800/90 backdrop-blur-sm border-b border-slate-600/60 pointer-events-none"
      role="status"
    >
      <span>{{ t('canvasPage.collaborationFooter') }}</span>
      <span class="opacity-60">·</span>
      <span class="font-mono">{{ workshopCode }}</span>
    </div>

    <!-- Main canvas area - merged chrome (top bar + toolbar) in CanvasChrome -->
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
          :fit-view-on-init="diagramStore.type !== 'concept_map'"
          :concept-map-initial-topic-fit="false"
          :hand-tool-active="handToolActive"
          :collab-locked-node-ids="collabLockedNodeIds"
          :presentation-rail-open="presentationRailOpen"
          @node-double-click="handleNodeDoubleClick"
        />
      </div>

      <!-- MindMate floating panel - rounded card, inset to clear floating toolbars -->
      <Transition name="mindmate-slide">
        <div
          v-if="panelsStore.mindmatePanel.isOpen"
          class="mindmate-panel-float fixed z-50 flex flex-col bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-xl overflow-hidden"
          :style="{
            width: `${PANEL.MINDMATE_WIDTH}px`,
            top: `${PANEL_INSET.TOP}px`,
            right: mindMatePanelRight,
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
            :presentation-rail-open="presentationRailOpen"
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

<style scoped src="./CanvasPage.scoped.css"></style>
