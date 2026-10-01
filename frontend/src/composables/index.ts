/**
 * Composables barrel — re-exports for `@/composables`.
 * Source files live under feature folders: `core/`, `editor/`, `workshop/`, `knowledge/`, `mindmate/`,
 * plus existing `diagrams/`, `nodePalette/`, `canvasPage/`, `canvasToolbar/`, `diagramCanvas/`, `queries/`, etc.
 */

// Core utilities
export { useEventBus, eventBus } from './core/useEventBus'
export type { EventTypes, EventKey, EventHandler, EventStats } from './core/useEventBus'
export { useSessionLifecycle, sessionLifecycle } from './core/useSessionLifecycle'
export type { Destroyable, SessionInfo, CleanupResult } from './core/useSessionLifecycle'
export { useSSE, useFetchSSE } from './core/useSSE'
export { useNotifications } from './core/useNotifications'
export { notify } from './core/notifications'
export { useLanguage } from './core/useLanguage'
export { swissGlassConfirm, swissGlassConfirmHero } from './common/useSwissGlassConfirm'
export { swissGlassPrompt } from './common/useSwissGlassPrompt'
export { getDiagramTypeDisplayName, getDefaultDiagramName } from './editor/useDiagramLabels'

// Keyboard helpers that do not import Vue Flow. Vue Flow shortcuts stay on
// `@/composables/core/useKeyboard` so this barrel does not pull the editor runtime.
export { useEditorKeyboard, createDefaultEditorHandlers } from './core/useEditorKeyboard'

// Canvas and interaction (diagram editor)
export { useSelection } from './editor/useSelection'
export { useInteraction, createVueFlowHandlers } from './editor/useInteraction'
export { useDiagramOperations, getDiagramOperations } from './editor/useDiagramOperations'
export { useKittyAgent } from './kitty/useKittyAgent'
export type { KittyAgentState, KittyAgentContext, KittyAgentOptions } from './kitty/useKittyAgent'
export { useKittyDesktopFocusHint, useKittyDesktopFocusPublish } from './kitty/useKittyDesktopFocus'
export { useMobileKittyPairing } from './kitty/useMobileKittyPairing'
export type {
  MobileKittyBootstrapPayload,
  MobileKittyContextPreview,
} from './kitty/useMobileKittyPairing'
export { useKittyDesktopActionPoll } from './kitty/useKittyDesktopActionPoll'
export { useCanvasKittyDesktopPairing } from './kitty/useCanvasKittyDesktopPairing'
export { useKittyDesktopRemoteSync } from './kitty/useKittyDesktopRemoteSync'
export { useKittyDesktopLiveSpecSync } from './kitty/useKittyDesktopLiveSpecSync'
export { useKittyDesktopDiagramUpdateBridge } from './kitty/useKittyDesktopDiagramUpdateBridge'
export { KITTY_DESKTOP_PAIR_WAIT_SEC } from './kitty/runKittyIntervalPoll'
export {
  buildKittyDiagramContext,
  buildKittyContextPreferStore,
  buildStandaloneKittyLandingContext,
} from './kitty/buildKittyDiagramContext'
export { useMindMate, simpleMarkdown } from './mindmate/useMindMate'
export { useHistory, useHistoryKeyboard } from './editor/useHistory'
export { useViewManager, createVueFlowViewport } from './editor/useViewManager'
export { usePanelCoordination, getPanelCoordinator } from './editor/usePanelCoordination'
export { getNodePalette } from './nodePalette/useNodePalette'
export { getAiBrainstorm } from './aiBrainstorm/useAiBrainstorm'
export { useDragConstraints } from './editor/useDragConstraints'
export { useNodeActions } from './editor/useNodeActions'
export type { UseNodeActionsOptions } from './editor/useNodeActions'
export { useTheme } from './core/useTheme'
export { useVersionCheck } from './core/useVersionCheck'
export type { VersionCheckOptions } from './core/useVersionCheck'
export { useDiagramExport } from './editor/useDiagramExport'
export { useDiagramImport } from './editor/useDiagramImport'
export { useDiagramSpecForSave, useDiagramSpecForPersist } from './editor/useDiagramSpecForSave'
export { useDiagramAutoSave } from './editor/useDiagramAutoSave'
export { useFeatureFlags } from './core/useFeatureFlags'
export { usePublicSiteUrl } from './core/usePublicSiteUrl'
export type { UseDiagramAutoSaveOptions, SaveFlushResult } from './editor/useDiagramAutoSave'
export type { UseDiagramExportOptions } from './editor/useDiagramExport'
export { useNodeDimensions } from './editor/useNodeDimensions'
export { useInlineEdit } from './editor/useInlineEdit'
export type { InlineEditOptions } from './editor/useInlineEdit'
export { useAutoComplete } from './editor/useAutoComplete'
export { isPlaceholderText } from './editor/placeholderText'
export {
  useConceptMapRelationship,
  CONCEPT_MAP_GENERATING_KEY,
} from './editor/useConceptMapRelationship'
export { useInlineRecommendations } from './editor/useInlineRecommendations'
export { useInlineRecommendationsCoordinator } from './editor/useInlineRecommendationsCoordinator'
export { useWorkshop } from './workshop/useWorkshop'
export type { WorkshopUpdate } from './workshop/useWorkshop'
export { useSnapshotHistory } from './editor/useSnapshotHistory'
export type {
  SnapshotMetadata,
  SnapshotTakeResult,
  SnapshotRecallResult,
  SnapshotDeleteResult,
} from './editor/useSnapshotHistory'

export { useAsyncFetch, useAuthFetch, useAsyncAction, useAsyncPost } from './core/useAsyncApi'
export type { AsyncFetchOptions, AsyncActionOptions } from './core/useAsyncApi'

// Mobile detection
export { useMobileDetect } from './core/useMobileDetect'

// Diagram-specific composables (per-type layout)
export * from './diagrams'

// Canvas toolbar (formatting + More apps)
export * from './canvasToolbar'

// Sidebar + teacher usage (optional deep-imports; re-exported for convenience)
export {
  appSidebarInjectionKey,
  useAppSidebar,
  type AppSidebarContext,
} from './sidebar/useAppSidebar'
