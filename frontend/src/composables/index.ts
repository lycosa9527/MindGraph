/**
 * Composables Index
 */

// Core utilities
export { useEventBus, eventBus } from './useEventBus'
export type { EventTypes, EventKey, EventHandler, EventStats } from './useEventBus'
export { useSessionLifecycle, sessionLifecycle } from './useSessionLifecycle'
export type { Destroyable, SessionInfo, CleanupResult } from './useSessionLifecycle'
export { useSSE, useFetchSSE } from './useSSE'
export { useNotifications } from './useNotifications'
export { notify } from './notifications'
export { useLanguage } from './useLanguage'
export { getDiagramTypeDisplayName, getDefaultDiagramName } from './useDiagramLabels'

// Keyboard and input
export { useKeyboard, useEditorShortcuts, useVueFlowKeyboard } from './useKeyboard'
export type { KeyboardShortcut, UseVueFlowKeyboardOptions } from './useKeyboard'
export { useEditorKeyboard, createDefaultEditorHandlers } from './useEditorKeyboard'

// Canvas and interaction
export { useSelection } from './useSelection'
export { useInteraction, createVueFlowHandlers } from './useInteraction'
export { useDiagramOperations, getDiagramOperations } from './useDiagramOperations'
export { useVoiceAgent } from './useVoiceAgent'
export { useMindMate, simpleMarkdown } from './useMindMate'
export { useHistory, useHistoryKeyboard } from './useHistory'
export { useViewManager, createVueFlowViewport } from './useViewManager'
export { usePanelCoordination, getPanelCoordinator } from './usePanelCoordination'
export { getNodePalette } from './useNodePalette'
export { useDragConstraints } from './useDragConstraints'
export { useBranchMoveDrag } from './useBranchMoveDrag'
export { useNodeActions } from './useNodeActions'
export type { BranchMoveState, DropTarget } from './useBranchMoveDrag'
export { useTheme } from './useTheme'
export { useVersionCheck } from './useVersionCheck'
export type { VersionCheckOptions } from './useVersionCheck'
export { useDiagramExport } from './useDiagramExport'
export { useDiagramImport } from './useDiagramImport'
export { useDiagramSpecForSave } from './useDiagramSpecForSave'
export { useDiagramAutoSave } from './useDiagramAutoSave'
export { useFeatureFlags } from './useFeatureFlags'
export { usePublicSiteUrl } from './usePublicSiteUrl'
export type { UseDiagramAutoSaveOptions, SaveFlushResult } from './useDiagramAutoSave'
export type { UseDiagramExportOptions } from './useDiagramExport'
export { useNodeDimensions } from './useNodeDimensions'
export { useInlineEdit } from './useInlineEdit'
export type { InlineEditOptions } from './useInlineEdit'
export { useAutoComplete, isPlaceholderText } from './useAutoComplete'
export { useConceptMapRelationship, CONCEPT_MAP_GENERATING_KEY } from './useConceptMapRelationship'
export { useInlineRecommendations } from './useInlineRecommendations'
export { useInlineRecommendationsCoordinator } from './useInlineRecommendationsCoordinator'
export { useWorkshop } from './useWorkshop'
export type { WorkshopUpdate } from './useWorkshop'
export { useSnapshotHistory } from './useSnapshotHistory'
export type { SnapshotMetadata } from './useSnapshotHistory'

// VueFlow + VueUse integration
export { useCanvasState } from './useCanvasState'
export type { UseCanvasStateOptions, CanvasState } from './useCanvasState'
export { useDiagramPersistence } from './useDiagramPersistence'
export type { UseDiagramPersistenceOptions, DiagramPersistenceState } from './useDiagramPersistence'
export { useAsyncFetch, useAuthFetch, useAsyncAction, useAsyncPost } from './useAsyncApi'
export type { AsyncFetchOptions, AsyncActionOptions } from './useAsyncApi'

// Mobile detection
export { useMobileDetect } from './useMobileDetect'

// Diagram-specific composables
export * from './diagrams'
