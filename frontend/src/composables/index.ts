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

// Keyboard and input
export { useKeyboard, useEditorShortcuts } from './useKeyboard'
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

// Diagram-specific composables
export * from './diagrams'
