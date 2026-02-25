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
export { useDragConstraints } from './useDragConstraints'
export { useTheme } from './useTheme'
export { useVersionCheck } from './useVersionCheck'
export type { VersionCheckOptions } from './useVersionCheck'
export { useDiagramExport } from './useDiagramExport'
export type { UseDiagramExportOptions } from './useDiagramExport'
export { useInlineEdit } from './useInlineEdit'
export type { InlineEditOptions } from './useInlineEdit'
export { useAutoComplete, isPlaceholderText } from './useAutoComplete'
export { useIMEAutocomplete } from './useIMEAutocomplete'
export { useWorkshop } from './useWorkshop'
export type { WorkshopUpdate } from './useWorkshop'
export type {
  IMESuggestion,
  IMEAutocompleteOptions,
  IMEAutocompleteState,
} from './useIMEAutocomplete'

// VueFlow + VueUse integration
export { useCanvasState } from './useCanvasState'
export type { UseCanvasStateOptions, CanvasState } from './useCanvasState'
export { useDiagramPersistence } from './useDiagramPersistence'
export type { UseDiagramPersistenceOptions, DiagramPersistenceState } from './useDiagramPersistence'
export { useAsyncFetch, useAuthFetch, useAsyncAction, useAsyncPost } from './useAsyncApi'
export type { AsyncFetchOptions, AsyncActionOptions } from './useAsyncApi'

// Diagram-specific composables
export * from './diagrams'
