<script setup lang="ts">
/**
 * CanvasPage - Full canvas editor page with Vue Flow integration
 *
 * Store cleanup on exit (onUnmounted): diagram, savedDiagrams, llmResults, panels,
 * inline recommendations + relationship (via coordinator teardown), concept-map
 * focus/root review streams, snapshot history, presentation state, and partial
 * ui reset — avoids stale state and lingering SSE on re-entry.
 *
 * In-session reset (top-bar Reset): applyCanvasSessionReset + diagram:reset_requested
 * mirrors the same teardown without leaving the page.
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
 * - LLM generating: skip routine auto-save; persist after each model on llm:model_completed
 * - LLM all done: final flush on llm:generation_completed
 * - Auto-updates if diagram is already in library; auto-saves new if slots available
 */
import { computed, nextTick, onMounted, onUnmounted, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import { ElMessageBox } from 'element-plus'

import {
  AIModelSelector,
  CanvasChrome,
  CanvasMindMapShortcutGuide,
  CanvasTopBar,
  ConceptMapFocusReviewPicker,
  ConceptMapLabelPicker,
  ConceptMapRootConceptPicker,
  InlineRecommendationsPicker,
  MindMapPresentationSideToolbar,
  MindMapSidePanel,
  MindMapSideToolbar,
  MindMapSlideOverlay,
  PresentationTimerHud,
  PresentationTimerOverlay,
  ZoomControls,
} from '@/components/canvas'
import CanvasCollabOverlay from '@/components/canvas/CanvasCollabOverlay.vue'
import CanvasTranslateProgressBanner from '@/components/canvas/CanvasTranslateProgressBanner.vue'
import LearningSheetExportNudge from '@/components/canvas/LearningSheetExportNudge.vue'
import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import KittyCanvasAnchor from '@/components/kitty/KittyCanvasAnchor.vue'
import KittyDesktopVoiceCommandLog from '@/components/kitty/KittyDesktopVoiceCommandLog.vue'
import KittyDesktopWorkflowDebugLog from '@/components/kitty/KittyDesktopWorkflowDebugLog.vue'
import { MindmatePanel, NodePalettePanel, RootConceptModal } from '@/components/panels'
import {
  eventBus,
  getDiagramOperations,
  getNodePalette,
  getPanelCoordinator,
  useCanvasKittyDesktopPairing,
  useDiagramSpecForSave,
  useEventBus,
  useInlineRecommendations,
  useInlineRecommendationsCoordinator,
  useKittyDesktopRemoteSync,
  useLanguage,
  useNotifications,
  useSnapshotHistory,
} from '@/composables'
import { useSchoolTierFeatures } from '@/composables/auth/useSchoolTierFeatures'
import {
  applyCanvasKittySeedFromRoute,
  canvasKittySeedQueryKeysPresent,
} from '@/composables/canvasPage/applyCanvasKittySeedFromRoute'
import {
  VALID_DIAGRAM_TYPES,
  diagramTypeMap,
  diagramTypeToChineseMap,
} from '@/composables/canvasPage/diagramTypeMaps'
import { isNodeEligibleForInlineRec } from '@/composables/canvasPage/inlineRecEligibility'
import { registerCanvasPageDiagramEventBus } from '@/composables/canvasPage/registerCanvasPageDiagramEventBus'
import { registerCanvasPageResetHandler } from '@/composables/canvasPage/registerCanvasPageResetHandler'
import { useCanvasPageEditorShortcuts } from '@/composables/canvasPage/useCanvasPageEditorShortcuts'
import { useCanvasPageLibrarySnapshots } from '@/composables/canvasPage/useCanvasPageLibrarySnapshots'
import { useCanvasPageMountedHandlers } from '@/composables/canvasPage/useCanvasPageMountedHandlers'
import { useCanvasPagePresentation } from '@/composables/canvasPage/useCanvasPagePresentation'
import { useCanvasPageTabRecIndicator } from '@/composables/canvasPage/useCanvasPageTabRecIndicator'
import { useCanvasPageWorkshopCollab } from '@/composables/canvasPage/useCanvasPageWorkshopCollab'
import { useConceptMapRelationshipTabFromSelection } from '@/composables/canvasPage/useConceptMapRelationshipTabFromSelection'
import {
  canvasVirtualKeyboardOpen,
  ensureCanvasVirtualKeyboardUiVersionSync,
  toggleCanvasVirtualKeyboard,
} from '@/composables/canvasToolbar'
import { useCanvasToolbarApps } from '@/composables/canvasToolbar/useCanvasToolbarApps'
import {
  bindMindMapExternalPanelClose,
  useMindMapSideToolbarState,
} from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import {
  diagramSpecLikelyNeedsMarkdownPipeline,
  loadDiagramMarkdownPipeline,
} from '@/composables/core/diagramMarkdownPipeline'
import { useDiagramAutoSave } from '@/composables/editor/useDiagramAutoSave'
import { useMindMapRagBranchExpand } from '@/composables/editor/useMindMapRagBranchExpand'
import { DOC_SUMMARY_LITE_UI } from '@/config/docSummaryLite'
import {
  createFileCenterActivePackage,
  FILE_CENTER_ACTIVE_PACKAGE_KEY,
} from '@/composables/fileCenter/useFileCenterActivePackage'
import { handleKittyAddNodeWithRecommendationsRequest } from '@/composables/kitty/kittyAddNodeWithRecommendations'
import { resolveKittyChildNodeId } from '@/composables/kitty/kittyDiagramChildren'
import { useKittyDesktopVoiceCommandLog } from '@/composables/kitty/useKittyDesktopVoiceCommandLog'
import { useKittyDesktopWorkflowDebug } from '@/composables/kitty/useKittyDesktopWorkflowDebug'
import { useKittyDiagramReviewAnnotationBus } from '@/composables/kitty/useKittyDiagramReviewAnnotationBus'
import { useKittyVoiceSelectionBus } from '@/composables/kitty/useKittyVoiceSelectionBus'
import { useMindMapSlidePresentation } from '@/composables/mindMap/useMindMapSlidePresentation'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import {
  learningSheetNeedsPresentationConfirm,
  resetLearningSheetCustomModeUi,
  resumeLearningSheetAfterPresentation,
  suspendLearningSheetForPresentation,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import {
  setPresentationDiagramEditLocked,
  setPresentationFullscreenRoot,
} from '@/composables/presentation/presentationDiagramEdit'
import { IMPORT_SPEC_KEY, SAVE } from '@/config'
import {
  PRESENTATION_HIGHLIGHTER_PALETTE_TOOLBAR,
} from '@/config/presentationHighlighter'
import {
  PRESENTATION_LASER_SIZE_SCALE,
  type PresentationLaserSize,
} from '@/config/presentationLaser'
import {
  PRESENTATION_BOARD_THICKNESS_SCALE,
  type PresentationBoardColorId,
  type PresentationBoardThickness,
  presentationBoardColorStroke,
} from '@/config/presentationPen'
import { FIT_PADDING, PANEL, PANEL_INSET } from '@/config/uiConfig'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { intlLocaleForUiCode } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'
import {
  type LLMResult,
  useAuthStore,
  useConceptMapRelationshipStore,
  useDiagramStore,
  useFeatureFlagsStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
  usePanelsStore,
  useUIStore,
} from '@/stores'
import { useConceptMapFocusReviewStore } from '@/stores/conceptMapFocusReview'
import { useConceptMapRootConceptReviewStore } from '@/stores/conceptMapRootConceptReview'
import { usePresentationPointerStore } from '@/stores/presentationPointer'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import type { MindMapPresentationToolId } from '@/types/diagram'
import { MIND_MAP_PRESENTATION_EXPANDABLE_TOOLS } from '@/types/diagram'
import { isMindMapDiagramType } from '@/utils/conceptMapDesktopViewport'
import { resolveDiagramTitleForSave } from '@/utils/diagramTitleForSave'

const route = useRoute()
const router = useRouter()
const diagramStore = useDiagramStore()
getDiagramOperations()
const relationshipStore = useConceptMapRelationshipStore()
const uiStore = useUIStore()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()
const llmResultsStore = useLLMResultsStore()
const panelsStore = usePanelsStore()
const { promptLanguage, t, currentLanguage } = useLanguage()
const notify = useNotifications()
const { canUseOnlineCollab, canUsePresentationTools } = useSchoolTierFeatures()
const featureFlagsStore = useFeatureFlagsStore()
const { handleAIGenerate, handleConceptGeneration, isAIGenerating } = useCanvasToolbarApps()

const snapshotHistory = useSnapshotHistory()
const recallingSnapshotVersion = snapshotHistory.recallingVersion

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
  timerHudVisible,
  onTimerToggleRun,
  onTimerReset,
  onTimerPresetMinutes,
  onTimerStartPresenting,
  onTimerCloseHud,
  onTimerExit,
  onTimerSetMinutes,
  laserCursorStyle,
  spotlightStyle,
  handleZoomChange,
  handleZoomIn,
  handleZoomOut,
  handleFitToScreen,
  handleHandToolToggle,
  suspendHandToolForPresentation,
  resumeHandToolAfterPresentation,
  handleStartPresentation,
  handleModelChange,
  resetPresentationStateOnLeave,
} = useCanvasPagePresentation()

ensureCanvasVirtualKeyboardUiVersionSync()

const presentationShortcutBus = useEventBus('CanvasPagePresentationShortcuts')
presentationShortcutBus.on('presentation:toggle_virtual_keyboard_requested', () => {
  toggleCanvasVirtualKeyboard()
})

const {
  workshopCode,
  workshopVisibility,
  activeEditors,
  collabLockedNodeIds,
  applyJoinWorkshopFromQuery,
  applyWorkshopCodeFromSession,
  checkAndReconnectWorkshop,
  resetPreviousDiagramTracking,
  participantsWithNames,
  ownerUsername,
  remoteHostDisplayedLlmModel,
  roomIdleSecondsRemaining,
  connectionStatus,
  reconnect,
  isDiagramOwner,
  workshopRole,
  isViewer,
  sessionDiagramId,
  sessionDiagramTitle,
} = useCanvasPageWorkshopCollab()

useCanvasPageTabRecIndicator()

const isCollabGuest = computed(() => workshopCode.value != null && !isDiagramOwner.value)

const currentDiagramId = computed(() => savedDiagramsStore.activeDiagramId ?? null)

const collabOverlayRef = ref<InstanceType<typeof CanvasCollabOverlay> | null>(null)

function handleOpenCollab(mode: 'organization' | 'network' | 'stop') {
  if (mode !== 'stop' && !canUseOnlineCollab.value) {
    notify.warning(t('auth.schoolTierFeatureUnavailable'))
    return
  }
  if (mode === 'stop') {
    void collabOverlayRef.value?.stopNow()
    return
  }
  collabOverlayRef.value?.openCollab(mode)
}

async function handleStartPresentationWithTier(): Promise<void> {
  if (!canUsePresentationTools.value) {
    notify.warning(t('auth.schoolTierFeatureUnavailable'))
    return
  }
  const opening = !presentationRailOpen.value
  if (opening && learningSheetNeedsPresentationConfirm()) {
    try {
      await ElMessageBox.confirm(
        t('canvas.presentation.learningSheetConfirmBody'),
        t('canvas.presentation.learningSheetConfirmTitle'),
        {
          confirmButtonText: t('canvas.presentation.learningSheetConfirmProceed'),
          cancelButtonText: t('common.cancel'),
          type: 'warning',
        }
      )
    } catch {
      return
    }
  }
  handleStartPresentation()
}

async function enterPresentationFullscreen(): Promise<void> {
  const el = canvasPageRef.value
  if (!el?.requestFullscreen) return
  try {
    if (document.fullscreenElement !== el) {
      await el.requestFullscreen()
    }
  } catch {
    /* user denied or unsupported */
  }
}

async function exitPresentationFullscreen(): Promise<void> {
  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    }
  } catch {
    /* ignore */
  }
}

function applyPenThickness(value: PresentationBoardThickness): void {
  penThickness.value = value
  presentationPointerStore.penScale = PRESENTATION_BOARD_THICKNESS_SCALE[value]
}

function applyPenColor(id: PresentationBoardColorId): void {
  penColorId.value = id
  presentationPenColor.value = presentationBoardColorStroke(id)
}

function applyLaserSize(size: PresentationLaserSize): void {
  presentationPointerStore.setScaleForTool('laser', PRESENTATION_LASER_SIZE_SCALE[size])
}

function applyHighlighterColor(index: number): void {
  highlighterColorIndex.value = index
  const entry = PRESENTATION_HIGHLIGHTER_PALETTE_TOOLBAR[index]
  if (entry) {
    presentationHighlighterColor.value = entry.stroke
  }
}

function applyHighlighterScale(scale: number): void {
  presentationPointerStore.setScaleForTool('highlighter', scale)
}

function toggleStrokeEraser(): void {
  presentationStrokeEraserActive.value = !presentationStrokeEraserActive.value
}

function handleMindMapPresentationToolSelect(tool: MindMapPresentationToolId): void {
  const current = mindMapPresentationTool.value
  if (tool === current) {
    if (
      (MIND_MAP_PRESENTATION_EXPANDABLE_TOOLS as readonly MindMapPresentationToolId[]).includes(
        tool
      ) ||
      tool === 'hand'
    ) {
      presentationStrokeEraserActive.value = false
      mindMapPresentationTool.value = 'pointer'
      return
    }
  }
  if (tool !== current) {
    presentationStrokeEraserActive.value = false
  }
  mindMapPresentationTool.value = tool
}

function handleMindMapPresentationExit(): void {
  handleStartPresentationWithTier()
}

function handleMindMapTimerExit(): void {
  onTimerExit()
  mindMapPresentationTool.value = useMindMapV2.value ? 'hand' : 'pointer'
  handToolActive.value = false
}

function handleMindMapTimerStartPresenting(): void {
  onTimerStartPresenting()
  mindMapPresentationTool.value = 'pointer'
  handToolActive.value = false
}

function handleMindMapTimerCloseHud(): void {
  onTimerCloseHud()
}

function handlePresentationEscape(event: KeyboardEvent): void {
  if (!showSimplifiedPresentationRail.value) return
  if (useMindMapV2.value && mindMapPresentationTool.value === 'slides') return
  if (event.key !== 'Escape') return
  const active = document.activeElement as HTMLElement
  if (active?.tagName === 'INPUT' || active?.tagName === 'TEXTAREA' || active?.isContentEditable) {
    return
  }
  event.preventDefault()
  handleStartPresentationWithTier()
}

function handleCollabSession(payload: {
  code: string | null
  visibility: 'organization' | 'network' | null
}) {
  eventBus.emit('workshop:code-changed', {
    code: payload.code,
    visibility: payload.visibility,
  })
}

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
  if (isMindMapPresentationMode.value) return false
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

const useMindMapV2 = useMindMapV2Chrome()

const isMindMapCanvas = computed(() => isMindMapDiagramType(diagramStore.type))

eventBus.onWithOwner(
  'mindmap:canvas_mode_changed',
  ({ previousMode, newMode }) => {
    if (isMindMapDiagramType(diagramStore.type)) {
      diagramStore.reconcileMindMapCanvasMode(previousMode, newMode)
    }
  },
  'CanvasPage'
)

const fitViewOnInit = computed(() => {
  const type = diagramStore.type
  if (type === 'concept_map') return false
  // V2 mind maps: one-shot fit on enter via useDiagramCanvasFit.handleNodesInitialized;
  // keep false here so node/panel watches do not auto-refit while editing.
  if (useMindMapV2.value) return false
  return true
})

const featureKnowledgeSpaceFlag = computed(() => featureFlagsStore.getFeatureKnowledgeSpace())
const fileCenterEnabled = computed(
  () => featureKnowledgeSpaceFlag.value && useMindMapV2.value
)
provide(
  FILE_CENTER_ACTIVE_PACKAGE_KEY,
  createFileCenterActivePackage(fileCenterEnabled)
)
const ragBranchExpandEnabled = computed(
  () => fileCenterEnabled.value && !DOC_SUMMARY_LITE_UI
)
useMindMapRagBranchExpand(ragBranchExpandEnabled)

const isMindMapPresentationMode = computed(
  () => useMindMapV2.value && presentationRailOpen.value && canUsePresentationTools.value
)

/** All diagram types use the simplified 4-tool presentation rail when open. */
const showSimplifiedPresentationRail = computed(
  () => presentationRailOpen.value && canUsePresentationTools.value
)

const mindMapPresentationTool = ref<MindMapPresentationToolId>('pointer')
const penColorId = ref<PresentationBoardColorId>('red')
const penThickness = ref<PresentationBoardThickness>('medium')
const presentationPenColor = ref(presentationBoardColorStroke('red'))
const highlighterColorIndex = ref(0)
const presentationStrokeEraserActive = ref(false)
const presentationPointerStore = usePresentationPointerStore()
const { laserScale, highlighterScale } = storeToRefs(presentationPointerStore)

const slidePresentation = useMindMapSlidePresentation({
  active: () => isMindMapPresentationMode.value && mindMapPresentationTool.value === 'slides',
  onExitPresentation: () => handleStartPresentationWithTier(),
})

const presentationPointerEditMode = computed(
  () => showSimplifiedPresentationRail.value && mindMapPresentationTool.value === 'pointer'
)

const presentationHandPanMode = computed(
  () => showSimplifiedPresentationRail.value && mindMapPresentationTool.value === 'hand'
)

watch(
  [showSimplifiedPresentationRail, mindMapPresentationTool, presentationRailOpen],
  () => {
    setPresentationDiagramEditLocked(
      showSimplifiedPresentationRail.value && mindMapPresentationTool.value !== 'pointer'
    )
  },
  { immediate: true }
)

watch(
  canvasPageRef,
  (el) => {
    setPresentationFullscreenRoot(el)
  },
  { immediate: true }
)

const showMindMapSlideOverlay = computed(
  () =>
    isMindMapPresentationMode.value &&
    mindMapPresentationTool.value === 'slides' &&
    slidePresentation.slideCount.value > 0
)

const showBottomBar = computed(() => !isMindMapPresentationMode.value)

const showMindMapShortcutGuide = computed(
  () => useMindMapV2.value && !presentationRailOpen.value && Boolean(diagramStore.data)
)

const showMindMapSideToolbar = computed(
  () =>
    useMindMapV2.value &&
    !presentationRailOpen.value &&
    Boolean(diagramStore.data) &&
    !isViewer.value
)

const showLearningSheetExportNudge = computed(
  () => useMindMapV2.value && !isMindMapPresentationMode.value && !isViewer.value
)

const { activeTool, sidebarVisible, closeActiveTool } = useMindMapSideToolbarState()

watch(
  () => useMindMapV2.value && panelsStore.conceptParkingLotPanel.isOpen,
  (shouldShowWaterfallPanel) => {
    if (shouldShowWaterfallPanel && activeTool.value !== 'waterfall') {
      activeTool.value = 'waterfall'
    }
  }
)

bindMindMapExternalPanelClose(() => panelsStore.conceptParkingLotPanel.isOpen, closeActiveTool)

watch(
  () => diagramStore.type,
  () => {
    closeActiveTool()
  }
)

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

const { showKittyDesktopIndicator } = useCanvasKittyDesktopPairing({
  currentDiagramId,
  hasDiagramContent: computed(() => diagramStore.data != null),
  authIsAuthenticated: computed(() => authStore.isAuthenticated),
  isViewer: computed(() => isViewer.value),
  kittyFeatureEnabled: computed(() => featureFlagsStore.getFeatureKittyAgent()),
  onLibraryScopeSwitchedCleanup: (oldScope: string) => {
    if (authStore.isAuthenticated && featureFlagsStore.getFeatureKittyAgent()) {
      fetch(`/api/kitty/cleanup/${encodeURIComponent(oldScope)}`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
      }).catch(() => {})
    }
  },
})

const { entries: kittyVoiceCommandEntries } = useKittyDesktopVoiceCommandLog({
  enabled: showKittyDesktopIndicator,
  scopeId: currentDiagramId,
})

const { entries: kittyWorkflowDebugEntries } = useKittyDesktopWorkflowDebug({
  enabled: showKittyDesktopIndicator,
  scopeId: currentDiagramId,
})

const kittyRemoteSyncEnabled = computed(
  () =>
    featureFlagsStore.getFeatureKittyAgent() &&
    authStore.isAuthenticated &&
    !isViewer.value &&
    currentDiagramId.value != null &&
    currentDiagramId.value !== ''
)

useKittyDesktopRemoteSync({
  libraryDiagramId: currentDiagramId,
  syncEnabled: kittyRemoteSyncEnabled,
  collabSessionActive: computed(() => diagramStore.collabSessionActive),
})

useConceptMapRelationshipTabFromSelection({ startRecommendations })

useCanvasPageMountedHandlers({
  snapshotHistory,
  startRecommendations,
  startNodePaletteSession,
  isDiagramOwner,
})

useKittyDiagramReviewAnnotationBus('CanvasPage')
useKittyVoiceSelectionBus('CanvasPage')

eventBus.onWithOwner(
  'diagram:auto_complete_requested',
  () => {
    if (!authStore.isAuthenticated) {
      notify.warning(t('notification.signInToUse'))
      return
    }
    if (diagramStore.collabSessionActive && diagramStore.type !== 'concept_map') {
      notify.warning(t('canvas.toolbar.collabLiveAiDisabled'))
      return
    }
    if (isAIGenerating.value) return
    if (diagramStore.type === 'concept_map') {
      handleConceptGeneration()
      return
    }
    void handleAIGenerate()
  },
  'CanvasPage'
)

eventBus.onWithOwner(
  'kitty:inline_recommendations_requested',
  (data: { nodeId?: string; nodeIndex?: number }) => {
    const nodes = diagramStore.data?.nodes ?? []
    let nid = resolveKittyChildNodeId(diagramStore.type, nodes, {
      nodeId: data.nodeId,
      nodeIndex: data.nodeIndex,
    })
    if (!nid) nid = diagramStore.selectedNodes[0]
    if (!nid) {
      notify.warning(t('canvas.toolbar.selectNodesToDelete', '请先选择一个节点'))
      return
    }
    const node = nodes.find((x) => x.id === nid)
    if (
      !node ||
      !isNodeEligibleForInlineRec(diagramStore.type, node, diagramStore.data?.connections)
    ) {
      notify.warning(t('notification.nodeNotEligible'))
      return
    }
    if (diagramStore.type === 'concept_map' && !llmResultsStore.selectedModel) {
      notify.warning(t('notification.conceptMapTabNeedsAi'))
      return
    }
    if (!authStore.isAuthenticated) {
      notify.warning(t('notification.signInToUse'))
      return
    }
    void startRecommendations(nid)
  },
  'CanvasPage'
)

eventBus.onWithOwner(
  'kitty:add_node_with_recommendations_requested',
  (data: { text?: string }) => {
    void handleKittyAddNodeWithRecommendationsRequest({
      text: data.text,
      diagramStore,
      startRecommendations,
      inlineRecReady: inlineRecStore.isReady,
      isAuthenticated: authStore.isAuthenticated,
      conceptMapAiEnabled: Boolean(llmResultsStore.selectedModel),
      translate: t,
      notifyWarning: (message: string) => notify.warning(message),
    })
  },
  'CanvasPage'
)

function handleNodeDoubleClick(_node: { id?: string; type?: string }): void {
  // Double-click only enters edit mode. Inline recommendations are triggered by Tab
  // when user is editing a node (see node_editor:tab_pressed listener).
}

// Auto-save: event-driven, config-based (useDiagramAutoSave)
// Collab guests must not auto-save: their edits belong to the host's session diagram,
// saving a copy would change activeDiagramId, mutate the URL, and trigger
// loadDiagramFromLibrary which overwrites the live collab view.
// The host's autosave is also suppressed while a workshop is live: the server
// rejects REST PUT with 409 during an active session; changes are persisted
// through the WebSocket collab pipeline instead.
const isCollabActive = computed(() => diagramStore.collabSessionActive)
const diagramAutoSave = useDiagramAutoSave({ isCollabGuest, isCollabActive })

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
  useCanvasPageLibrarySnapshots({ diagramAutoSave, snapshotHistory, isDiagramOwner })

function normalizedRouteDiagramId(): string | undefined {
  const raw = route.query.diagramId ?? route.query.diagram_id
  if (typeof raw === 'string') {
    return raw
  }
  if (Array.isArray(raw) && raw[0]) {
    return raw[0]
  }
  return undefined
}

/** Keep snapshot badges aligned with saved diagram id and URL (import/collab paths). */
watch(
  () => [savedDiagramsStore.activeDiagramId, normalizedRouteDiagramId()] as const,
  async ([activeId, routeId]) => {
    if (!activeId) {
      if (!routeId) {
        snapshotHistory.clearSnapshots()
      }
      return
    }
    if (routeId && routeId !== activeId) {
      snapshotHistory.clearSnapshots()
      return
    }
    await snapshotHistory.loadSnapshots(activeId)
  },
  { flush: 'post' }
)

registerCanvasPageDiagramEventBus({ canvasZoom })

registerCanvasPageResetHandler({
  snapshotHistory,
  diagramAutoSave,
  resetPresentationStateOnLeave,
  exitPresentationFullscreen,
  presentationRailOpen,
  mindMapPresentationTool,
  slidePresentation,
  canvasZoom,
})

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
    if (open) {
      suspendHandToolForPresentation()
      suspendLearningSheetForPresentation()
    } else {
      resumeHandToolAfterPresentation()
      resumeLearningSheetAfterPresentation()
    }
    if (open && useMindMapV2.value) {
      closeActiveTool()
      mindMapPresentationTool.value = 'pointer'
      void enterPresentationFullscreen()
      void nextTick(() => {
        eventBus.emit('view:fit_to_canvas_requested', { animate: true, userInitiated: true })
      })
    } else if (open) {
      mindMapPresentationTool.value = 'laser'
      presentationTool.value = 'laser'
    } else {
      mindMapPresentationTool.value = 'pointer'
      slidePresentation.reset()
      if (useMindMapV2.value) {
        void exitPresentationFullscreen()
      }
    }
  },
  { flush: 'sync' }
)

watch(mindMapPresentationTool, (tool) => {
  if (!showSimplifiedPresentationRail.value) return
  if (tool === 'slides' && !useMindMapV2.value) {
    mindMapPresentationTool.value = 'laser'
    return
  }
  if (tool === 'pen') {
    presentationTool.value = 'pen'
    handToolActive.value = false
    slidePresentation.stopSlideShow()
    return
  }
  if (tool === 'highlighter') {
    presentationTool.value = 'highlighter'
    handToolActive.value = false
    slidePresentation.stopSlideShow()
    return
  }
  if (tool === 'timer') {
    presentationTool.value = 'timer'
    handToolActive.value = false
    slidePresentation.stopSlideShow()
    return
  }
  if (tool === 'laser') {
    presentationTool.value = 'laser'
    handToolActive.value = false
    slidePresentation.stopSlideShow()
    return
  }
  if (tool === 'hand') {
    presentationTool.value = 'laser'
    handToolActive.value = false
    slidePresentation.stopSlideShow()
    return
  }
  if (tool === 'pointer') {
    presentationTool.value = 'laser'
    handToolActive.value = false
    slidePresentation.stopSlideShow()
    return
  }
  if (tool === 'slides') {
    presentationTool.value = 'laser'
    handToolActive.value = false
    slidePresentation.startSlideShow()
    return
  }
  if (tool === 'spotlight') {
    presentationTool.value = 'spotlight'
    handToolActive.value = false
    slidePresentation.stopSlideShow()
    return
  }
  if (tool === 'timer') {
    presentationTool.value = 'timer'
    handToolActive.value = false
    slidePresentation.stopSlideShow()
  }
})

watch(showSimplifiedPresentationRail, (active) => {
  if (active) {
    window.addEventListener('keydown', handlePresentationEscape, true)
  } else {
    window.removeEventListener('keydown', handlePresentationEscape, true)
  }
})

watch(canUsePresentationTools, (allowed) => {
  if (!allowed) {
    resetPresentationStateOnLeave()
  }
})

watch(canUseOnlineCollab, (allowed) => {
  if (!allowed) {
    sessionStorage.removeItem('mg_workshop_code')
    sessionStorage.removeItem('mg_workshop_diagram_id')
  }
})

const { handleSaveKey } = useCanvasPageEditorShortcuts({
  workshopCode,
  activeEditors,
  relationshipActiveEntry,
  diagramAutoSave,
  isCollabGuest,
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
      const loaded = await loadDiagramFromLibrary(newId)
      if (loaded) {
        void checkAndReconnectWorkshop(newId)
      }
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

  // Fetch diagrams to know current slot count
  await savedDiagramsStore.fetchDiagrams()

  // Priority 1: Guest joining a collab session via join_workshop query param.
  // The diagram spec arrives from the server via the WebSocket snapshot message —
  // do not attempt a library load (the diagram belongs to the host, not the guest).
  if (route.query.join_workshop) {
    if (!canUseOnlineCollab.value) {
      notify.warning(t('auth.schoolTierFeatureUnavailable'))
      const nextQuery = { ...route.query } as Record<string, string | string[] | undefined>
      delete nextQuery.join_workshop
      router.replace({ query: nextQuery })
      return
    }
    applyJoinWorkshopFromQuery()
    return
  }

  // Priority 1.5: Restore a guest workshop session after a page refresh.
  // applyJoinWorkshopFromQuery strips the ?join_workshop param from the URL, so
  // on a subsequent refresh the URL carries no trace of the session. sessionStorage
  // survives tab-level refreshes (but not tab close), making it the right scope.
  // If both keys are present, re-join the live session and skip the DB diagram load.
  // Guard: only restore when the URL does not request a different diagram — prevents
  // a stale code (e.g. from a session that ended with 1008) from hijacking navigation
  // to an unrelated diagram.
  {
    const savedCode = sessionStorage.getItem('mg_workshop_code')
    const savedDiagramId = sessionStorage.getItem('mg_workshop_diagram_id')
    const routeDiagramId =
      typeof route.query.diagramId === 'string'
        ? route.query.diagramId
        : typeof route.query.diagram_id === 'string'
          ? route.query.diagram_id
          : null
    const sessionMatchesRoute = !routeDiagramId || routeDiagramId === savedDiagramId
    if (savedCode && savedDiagramId && sessionMatchesRoute) {
      if (!canUseOnlineCollab.value) {
        sessionStorage.removeItem('mg_workshop_code')
        sessionStorage.removeItem('mg_workshop_diagram_id')
      } else {
        applyWorkshopCodeFromSession(savedCode, savedDiagramId)
        return
      }
    }
    if (savedCode && savedDiagramId && !sessionMatchesRoute) {
      sessionStorage.removeItem('mg_workshop_code')
      sessionStorage.removeItem('mg_workshop_diagram_id')
    }
  }

  // Priority 2: Load a saved diagram by ID from the library.
  const diagramIdRaw = route.query.diagramId ?? route.query.diagram_id
  const diagramId =
    typeof diagramIdRaw === 'string'
      ? diagramIdRaw
      : Array.isArray(diagramIdRaw)
        ? diagramIdRaw[0]
        : undefined
  if (diagramId) {
    const loaded = await loadDiagramFromLibrary(String(diagramId))
    if (loaded) {
      void checkAndReconnectWorkshop(String(diagramId))
    }
    return
  }

  // Priority 1b: Load imported diagram from `.mg` / `.cmap` (landing page Import button)
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
            const importTitle = resolveDiagramTitleForSave(
              diagramStore.effectiveTitle,
              diagramType,
              currentLanguage.value
            )
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
    applyCanvasKittySeedFromRoute(typeFromUrl, route.query, diagramStore)
    if (canvasKittySeedQueryKeysPresent(route.query)) {
      const restQuery = { ...route.query }
      delete restQuery.kitty_topic
      delete restQuery.kitty_left
      delete restQuery.kitty_right
      await router.replace({ path: route.path, query: restQuery })
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
  // User should navigate back and select a diagram type
})

onUnmounted(() => {
  void diagramAutoSave.flush().finally(() => {
    diagramAutoSave.teardown()
  })
  inlineRecCoordinator.teardown()
  eventBus.removeAllListenersForOwner('CanvasPage')

  // Cancel any in-flight concept-map 3-LLM review streams and clear their state.
  // Event-bus listeners that previously dismissed them (pane click / selection change)
  // are already removed above, so we must clear here to avoid stale state on re-entry.
  focusReviewStore.clear()
  rootConceptReviewStore.clear()

  // Clean up state when leaving canvas - matches old JS behavior
  diagramStore.reset()
  savedDiagramsStore.clearActiveDiagram()
  snapshotHistory.clearSnapshots()
  useLLMResultsStore().reset()
  usePanelsStore().reset()
  useMindMapSubgraphPreviewStore().clear()
  uiStore.setSelectedChartType('选择具体图示')
  uiStore.setFreeInputValue('')
  resetPresentationStateOnLeave()
  resetLearningSheetCustomModeUi()
  setPresentationDiagramEditLocked(false)
  setPresentationFullscreenRoot(null)
  void exitPresentationFullscreen()
  resetPreviousDiagramTracking()
})
</script>

<template>
  <div
    ref="canvasPageRef"
    class="canvas-page flex flex-col h-screen bg-gray-50 relative"
    :class="{
      'presentation-active': canUsePresentationTools && presentationRailOpen,
      'mind-map-presentation-active': isMindMapPresentationMode,
      'presentation-pointer-mode':
        showSimplifiedPresentationRail && mindMapPresentationTool === 'pointer',
      'presentation-hand-mode':
        showSimplifiedPresentationRail && mindMapPresentationTool === 'hand',
      'presentation-slides-mode':
        showSimplifiedPresentationRail && mindMapPresentationTool === 'slides',
      'presentation-highlighter-mode':
        showSimplifiedPresentationRail && mindMapPresentationTool === 'highlighter',
      'presentation-pen-mode':
        canUsePresentationTools && presentationRailOpen && mindMapPresentationTool === 'pen',
      'presentation-eraser-mode':
        canUsePresentationTools &&
        presentationRailOpen &&
        presentationStrokeEraserActive &&
        (mindMapPresentationTool === 'pen' || mindMapPresentationTool === 'highlighter'),
      'presentation-timer-mode':
        showSimplifiedPresentationRail && mindMapPresentationTool === 'timer',
    }"
  >
    <!-- Laser pointer cursor (presentation mode, laser tool) -->
    <Transition name="laser-fade">
      <div
        v-if="
          canUsePresentationTools && presentationRailOpen && mindMapPresentationTool === 'laser'
        "
        class="laser-cursor"
        :style="laserCursorStyle"
        aria-hidden="true"
      />
    </Transition>

    <!-- Spotlight overlay (new canvas presentation rail) -->
    <Transition name="spotlight-fade">
      <div
        v-if="
          isMindMapPresentationMode && mindMapPresentationTool === 'spotlight'
        "
        class="spotlight-overlay"
        :style="spotlightStyle"
        aria-hidden="true"
      />
    </Transition>

    <!-- Presentation timer (new canvas presentation rail) -->
    <PresentationTimerOverlay
      v-if="isMindMapPresentationMode && mindMapPresentationTool === 'timer'"
      :remaining-seconds="timerRemainingSeconds"
      :total-seconds="timerTotalSeconds"
      :running="timerRunning"
      @toggle-run="onTimerToggleRun"
      @reset="onTimerReset"
      @preset-minutes="onTimerPresetMinutes"
      @set-minutes="onTimerSetMinutes"
      @exit="handleMindMapTimerExit"
    />

    <!-- Simplified presentation rail: hand · laser · pen · spotlight · timer · slides (mind map) -->
    <MindMapPresentationSideToolbar
      v-if="showSimplifiedPresentationRail && mindMapPresentationTool !== 'timer'"
      :active-tool="mindMapPresentationTool"
      :color-id="penColorId"
      :thickness="penThickness"
      :laser-scale="laserScale"
      :highlighter-scale="highlighterScale"
      :highlighter-color-index="highlighterColorIndex"
      :stroke-eraser-active="presentationStrokeEraserActive"
      :show-slides-tool="useMindMapV2"
      @select-tool="handleMindMapPresentationToolSelect"
      @select-color="applyPenColor"
      @select-thickness="applyPenThickness"
      @select-laser-size="applyLaserSize"
      @select-highlighter-color="applyHighlighterColor"
      @select-highlighter-scale="applyHighlighterScale"
      @toggle-stroke-eraser="toggleStrokeEraser"
      @exit="handleMindMapPresentationExit"
    />

    <PresentationTimerOverlay
      v-if="showSimplifiedPresentationRail && mindMapPresentationTool === 'timer'"
      :remaining-seconds="timerRemainingSeconds"
      :total-seconds="timerTotalSeconds"
      :running="timerRunning"
      @toggle-run="onTimerToggleRun"
      @reset="onTimerReset"
      @exit="handleMindMapTimerExit"
      @preset-minutes="onTimerPresetMinutes"
      @set-minutes="onTimerSetMinutes"
      @start-presenting="handleMindMapTimerStartPresenting"
    />

    <PresentationTimerHud
      v-if="showSimplifiedPresentationRail && timerHudVisible"
      :remaining-seconds="timerRemainingSeconds"
      :running="timerRunning"
      @toggle-run="onTimerToggleRun"
      @reset="onTimerReset"
      @close="handleMindMapTimerCloseHud"
    />

    <MindMapSlideOverlay
      v-if="showMindMapSlideOverlay"
      :slide-index="slidePresentation.slideIndex.value"
      :slide-count="slidePresentation.slideCount.value"
      :slide-title="slidePresentation.currentSlide.value?.title ?? ''"
      :auto-play="slidePresentation.autoPlay.value"
      @toggle-auto-play="slidePresentation.toggleAutoPlay()"
      @prev="slidePresentation.prevSlide()"
      @next="slidePresentation.nextSlide()"
    />

    <CanvasChrome v-if="!isMindMapPresentationMode">
      <CanvasTopBar
        :auto-saved-status="autoSavedStatusText"
        :slot-full-and-new-diagram="isSlotsFullAndNewDiagram"
        :is-dirty="diagramAutoSave.isDirty.value"
        :is-saving="diagramAutoSave.isSaving.value"
        :snapshots="snapshotHistory.snapshots.value"
        :active-snapshot-version="snapshotHistory.activeSnapshotVersion.value"
        :recalling-snapshot-version="recallingSnapshotVersion"
        :workshop-code="workshopCode"
        :is-collab-guest="isCollabGuest"
        :is-viewer="isViewer"
        :workshop-role="workshopRole"
        @save-requested="handleSaveKey"
        @snapshot-recall="handleSnapshotRecall"
        @snapshot-delete="handleSnapshotDelete"
      />
    </CanvasChrome>

    <LearningSheetExportNudge v-if="showLearningSheetExportNudge" />

    <!-- Collab UI: participant rail, session modal, active-session banner -->
    <CanvasCollabOverlay
      ref="collabOverlayRef"
      :workshop-code="workshopCode"
      :workshop-visibility="workshopVisibility"
      :participants="participantsWithNames"
      :diagram-id="currentDiagramId"
      :session-diagram-id="sessionDiagramId"
      :session-diagram-title="sessionDiagramTitle"
      :owner-username="ownerUsername"
      :room-idle-remaining-seconds="roomIdleSecondsRemaining"
      :connection-status="connectionStatus"
      :is-collab-guest="isCollabGuest"
      @collabSession="handleCollabSession"
      @retryConnection="reconnect"
    />

    <CanvasTranslateProgressBanner />

    <KittyDesktopVoiceCommandLog
      :visible="showKittyDesktopIndicator"
      :entries="kittyVoiceCommandEntries"
    />

    <KittyDesktopWorkflowDebugLog
      :visible="showKittyDesktopIndicator"
      :entries="kittyWorkflowDebugEntries"
    />

    <KittyCanvasAnchor
      :visible="showKittyDesktopIndicator"
      state="active"
      variant="fab"
      :interactive="false"
    />

    <!-- Main canvas area - merged chrome (top bar + toolbar) in CanvasChrome -->
    <div class="flex-1 relative overflow-hidden flex flex-row min-h-0">
      <!-- Node Palette panel (瀑布流) - left 50%, inset to clear floating toolbars -->
      <Transition name="node-palette-slide">
        <div
          v-if="panelsStore.nodePalettePanel.isOpen && !isViewer && !useMindMapV2"
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
          v-model:presentation-pen-color="presentationPenColor"
          v-model:presentation-stroke-eraser-active="presentationStrokeEraserActive"
          class="w-full flex-1 min-h-0"
          :show-background="true"
          :show-minimap="false"
          :fit-view-on-init="fitViewOnInit"
          :concept-map-initial-topic-fit="false"
          :hand-tool-active="showSimplifiedPresentationRail ? presentationHandPanMode : handToolActive"
          :presentation-pointer-edit-mode="presentationPointerEditMode"
          :presentation-hand-pan-mode="presentationHandPanMode"
          :collab-locked-node-ids="collabLockedNodeIds"
          :presentation-rail-open="presentationRailOpen"
          @node-double-click="handleNodeDoubleClick"
        />

        <MindMapSideToolbar v-if="showMindMapSideToolbar && sidebarVisible" />
        <MindMapSidePanel
          v-if="showMindMapSideToolbar && activeTool"
          :tool="activeTool"
          @close="closeActiveTool"
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

    <!-- Bottom controls: shortcut guide (mind map) + floating glass toolbar card -->
    <div
      v-if="showBottomBar"
      class="canvas-bottom-controls absolute bottom-3 left-0 right-0 z-20 flex justify-center px-2 sm:px-4 pointer-events-none"
    >
      <div
        class="bottom-bar-cluster pointer-events-auto flex items-end gap-2 sm:gap-3 max-w-[95vw] min-w-0"
      >
        <CanvasMindMapShortcutGuide v-if="showMindMapShortcutGuide" />
        <div
          class="bottom-controls-card flex flex-col items-center md:flex-row md:flex-nowrap md:items-center gap-1.5 md:gap-0 rounded-xl shadow-lg p-1 md:p-1.5 border border-gray-200/80 dark:border-gray-600/80 bg-white/90 dark:bg-gray-800/90 backdrop-blur-md w-fit min-w-0 shrink-0"
        >
          <!-- shrink-0: AI block + focus picker width follows content (no flex-1 stretch) -->
          <div
            class="ai-selector-wrap flex shrink-0 justify-center md:justify-center min-w-0 order-2 md:order-1"
          >
            <AIModelSelector
              :host-displayed-llm-model="remoteHostDisplayedLlmModel"
              :is-collab-guest="isCollabGuest"
              @model-change="handleModelChange"
            />
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
            class="bottom-controls-divider hidden md:block order-1 md:order-2 w-px h-[22px] mx-2 bg-gray-200 dark:bg-gray-600 shrink-0 self-center"
          />
          <div
            v-if="showZoomControls"
            class="zoom-controls-wrap flex shrink-0 order-1 md:order-3"
          >
            <ZoomControls
              :zoom="canvasZoom"
              :hand-tool-active="handToolActive"
              :presentation-rail-open="presentationRailOpen"
              :workshop-code="workshopCode"
              :is-collab-guest="isCollabGuest"
              :allow-presentation-tools="canUsePresentationTools"
              :allow-online-collab="canUseOnlineCollab"
              @zoomChange="handleZoomChange"
              @zoomIn="handleZoomIn"
              @zoomOut="handleZoomOut"
              @fitToScreen="handleFitToScreen"
              @handToolToggle="handleHandToolToggle"
              @startPresentation="handleStartPresentationWithTier"
              @openCollab="handleOpenCollab"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped src="./CanvasPage.scoped.css"></style>
