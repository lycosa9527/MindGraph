/**
 * Enhanced Event Bus - Built on mitt with production features
 *
 * Features:
 * - Owner tracking for automatic cleanup (onWithOwner, removeAllListenersForOwner)
 * - Performance monitoring with threshold warnings
 * - Debug tools (getStats, getEventNames, getAllListeners, etc.)
 * - Full TypeScript support with event type definitions
 *
 * Migrated from archive/static/js/core/event-bus.js
 */
import { onUnmounted } from 'vue'

import mitt, { type Emitter, type Handler } from 'mitt'

// ============================================================================
// Event Type Definitions
// ============================================================================

/**
 * All event types in the application.
 * Add new events here for type safety.
 */
export type EventTypes = {
  // Panel Events
  'panel:open_requested': { panel: string; options?: Record<string, unknown>; source?: string }
  'panel:close_requested': { panel: string; source?: string }
  'panel:toggle_requested': { panel: string; source?: string }
  'panel:close_all_requested': { source?: string }
  'panel:opened': {
    panel: string
    isOpen: boolean
    options?: Record<string, unknown>
    source?: string
  }
  'panel:closed': { panel: string; isOpen: boolean; source?: string }
  'panel:error': { panel: string; error: string }
  'panel:all_closed': Record<string, never>
  'panel:coordinated_open': {
    panel: string
    source?: string
    options?: Record<string, unknown>
    previousPanel?: string
  }

  // Diagram Events
  'diagram:render_requested': { source?: string }
  'diagram:rendered': { diagramType: string; nodeCount?: number }
  'diagram:type_changed': { diagramType: string }
  'diagram:spec_updated': { spec: unknown }
  'diagram:operations_loaded': { diagramType: string; available?: string[] | boolean }
  'diagram:operations_unavailable': { diagramType: string; reason: string }
  'diagram:node_added': {
    node?: unknown
    category?: string
    diagramType?: string
    nodeType?: string
    nodeIndex?: number
  }
  'diagram:nodes_deleted': {
    nodeIds?: string[]
    deletedIds?: string[]
    deletedIndices?: number[]
    diagramType?: string
  }
  'diagram:delete_selected_requested': Record<string, never>
  'diagram:add_node_requested': Record<string, never>
  'diagram:node_updated': {
    nodeId: string
    updates: unknown
    diagramType?: string
    nodeType?: string
  }
  'diagram:operation_completed': {
    operation: string
    details?: unknown
    snapshot?: unknown
    spec?: unknown
  }
  'diagram:operation_warning': { message: string; operation?: string }
  'diagram:update_center': { source?: string; [key: string]: unknown }
  'diagram:update_nodes': { nodes: unknown[]; source?: string }
  'diagram:add_nodes': { nodes: unknown[]; source?: string }
  'diagram:remove_nodes': { nodeIds: unknown[]; source?: string }
  'diagram:auto_complete_requested': { source?: string; topic?: string; diagramType?: string }
  'diagram:position_saved': {
    nodeId: string
    position: { x: number; y: number }
    diagramType?: string
  }
  'diagram:positions_cleared': { diagramType?: string }
  'diagram:loaded': { diagramType: string; spec?: unknown }
  'diagram:update_requested': {
    updates?: unknown
    source?: string
    action?: string
    params?: unknown
  }

  // Canvas Events
  'canvas:generate_with_prompt': { prompt: string }

  // Voice Events
  'voice:start_requested': Record<string, never>
  'voice:stop_requested': Record<string, never>
  'voice:started': { sessionId: string }
  'voice:stopped': Record<string, never>
  'voice:connected': { sessionId: string }
  'voice:ws_closed': { code?: number; reason?: string; wasClean?: boolean }
  'voice:ws_error': { error: string; wsState?: unknown }
  'voice:transcription': { text: string }
  'voice:text_chunk': { text: string }
  'voice:audio_chunk': { audio: string }
  'voice:speech_started': { audioStartMs?: number }
  'voice:speech_stopped': { audioEndMs?: number }
  'voice:response_done': Record<string, never>
  'voice:action_executed': { action: string; params?: unknown }
  'voice:error': { error: string }
  'voice:destroyed': Record<string, never>
  'voice:cleanup_started': { diagramSessionId?: string }
  'voice:cleanup_backend_requested': { diagramSessionId?: string }
  'voice:cleanup_backend_completed': { diagramSessionId?: string }
  'voice:cleanup_backend_failed': { diagramSessionId?: string; error?: string }
  'voice:server_error': { error: string; code?: string }

  // History Events
  'history:undo_requested': Record<string, never>
  'history:redo_requested': Record<string, never>
  'history:undo_completed': {
    action?: string
    metadata?: unknown
    spec?: unknown
    historyIndex?: number
    canUndo?: boolean
    canRedo?: boolean
  }
  'history:redo_completed': {
    action?: string
    metadata?: unknown
    spec?: unknown
    historyIndex?: number
    canUndo?: boolean
    canRedo?: boolean
  }
  'history:undo_failed': { reason: string }
  'history:redo_failed': { reason: string }
  'history:saved': {
    action: string
    index?: number
    historySize?: number
    historyIndex?: number
    metadata?: unknown
    canUndo?: boolean
    canRedo?: boolean
  }
  'history:cleared': { canUndo?: boolean; canRedo?: boolean }
  'history:clear_requested': Record<string, never>
  'history:state_changed': {
    canUndo: boolean
    canRedo: boolean
    historyLength?: number
    historySize?: number
    historyIndex?: number
  }
  'history:restored': { snapshot?: unknown; spec?: unknown }

  // View Events
  'view:zoom_in_requested': Record<string, never>
  'view:zoom_out_requested': Record<string, never>
  'view:zoom_set_requested': { zoom: number }
  'view:fit_to_window_requested': { animate?: boolean }
  'view:fit_to_canvas_requested': { animate?: boolean }
  'view:fit_diagram_requested': Record<string, never>
  'view:flip_orientation_requested': Record<string, never>
  'view:zoomed': {
    scale?: number
    direction?: 'in' | 'out' | 'reset'
    level?: number
    zoom?: number
  }
  'view:fitted': { scale: number; translateX: number; translateY: number }
  'view:orientation_flipped': { orientation: string }
  'view:zoom_changed': {
    scale?: number
    direction?: 'in' | 'out' | 'reset'
    level?: number
    zoom?: number
    zoomPercent?: number
  }
  'view:pan_changed': { translateX?: number; translateY?: number; panX?: number; panY?: number }
  'view:fit_completed': {
    scale?: number
    translateX?: number
    translateY?: number
    method?: string
    mode?: string
    viewBox?: unknown
    animate?: boolean
    panelWidth?: number
  }
  'view:fit_for_export_requested': Record<string, never>
  'view:zoom_reset_requested': Record<string, never>

  // Interaction Events
  'interaction:selection_changed': { selectedNodes: string[] }
  'interaction:drag_started': { nodeId: string; position: { x: number; y: number } }
  'interaction:drag_ended': { nodeId: string; position: { x: number; y: number } }
  'interaction:handlers_attached': Record<string, never>
  'interaction:clear_selection_requested': Record<string, never>
  'interaction:select_node_requested': { nodeId?: string; nodeIndex?: number }
  'interaction:edit_text_requested': { nodeId: string }
  'node_editor:opening': { nodeId: string }
  'node_editor:closed': { nodeId: string }

  // Workshop Events
  'workshop:code-changed': { code: string | null }

  // Selection Events
  'selection:changed': { selectedNodes: unknown[] }
  'selection:cleared': { previousSelection?: string[] }
  'selection:select_requested': { nodeId?: string; nodeIndex?: number }
  'selection:highlight_requested': { nodeId: string }

  // Property Panel Events
  'property_panel:open_requested': { nodeId: string }
  'property_panel:close_requested': Record<string, never>
  'property_panel:clear_requested': Record<string, never>
  'property_panel:update_requested': { updates: unknown }
  'property_panel:opened': { nodeId: string }
  'property_panel:closed': Record<string, never>
  'property_panel:changed': { property: string; value: unknown }

  // Auth Events
  'auth:session_expired': { message?: string }

  // MindMate Events
  'mindmate:opened': { diagramSessionId?: string }
  'mindmate:closed': Record<string, never>
  'mindmate:send_message': { message: string }
  'mindmate:message_sending': { message: string; files?: unknown[] }
  'mindmate:message_chunk': { chunk: string }
  'mindmate:message_completed': { conversationId?: string }
  'mindmate:error': { error: string }
  'mindmate:stream_error': { error: string | undefined; error_type?: string; message?: string }
  'mindmate:file_uploaded': { file: unknown }
  'mindmate:file_received': { id?: string; type?: string; url?: string; belongs_to?: string }
  'mindmate:workflow_event': {
    event: string
    workflow_run_id?: string
    task_id?: string
    data?: Record<string, unknown>
  }
  'mindmate:tts_chunk': { data?: Record<string, unknown> }
  'mindmate:tts_complete': Record<string, never>
  'mindmate:suggested_questions': { questions: string[] }
  'mindmate:feedback_submitted': {
    messageId: string
    difyMessageId: string
    rating: 'like' | 'dislike' | null
  }
  'mindmate:conversation_changed': {
    conversationId: string | null
    title?: string
  }
  'mindmate:start_new_conversation': Record<string, never>
  'mindmate:title_updated': {
    conversationId: string | null
    title: string
    oldTitle?: string
  }

  // LLM Events
  'llm:generation_started': {
    models?: string[]
    diagramType?: string
    mainTopic?: string | null
    language?: string
  }
  'llm:generation_completed': {
    successCount?: number
    totalCount?: number
    allFailed?: boolean
  }
  'llm:generation_failed': { error: string }
  'llm:model_completed': { model?: string }
  'llm:first_result_available': { model?: string; elapsedTime?: number }
  'llm:result_rendered': { model?: string; diagramType?: string | null; nodeCount?: number }
  'llm:topic_identified': { topic: string }
  'llm:nodes_extracted': { nodes: unknown[] }
  'llm:spec_validated': { isValid: boolean }
  'llm:consistency_analyzed': Record<string, never>
  'llm:identify_topic_requested': { prompt: string }
  'llm:extract_nodes_requested': { topic: string }
  'llm:validate_spec_requested': { spec: unknown }
  'llm:analyze_consistency_requested': { spec?: unknown }

  // Autocomplete Events
  'autocomplete:start_requested': { options?: unknown }
  'autocomplete:render_cached_requested': Record<string, never>
  'autocomplete:update_button_states_requested': Record<string, never>
  'autocomplete:cancel_requested': Record<string, never>
  'autocomplete:completed': { success: boolean; error?: string }

  // Lifecycle Events
  'lifecycle:session_starting': { sessionId: string }
  'lifecycle:session_ending': { sessionId?: string; diagramType?: string; managerCount?: number }
  'session:register_requested': { manager: unknown; name: string }
  'session:validate_requested': { operation?: string }
  'session:validation_result': { isValid: boolean }
  'session:cleanup_requested': { sessionId?: string }
  'session:registered': { name: string }
  'session:cleanup_completed': { cleanedCount: number }
  'session:old_instance_cleanup': { count: number }
  'session:validated': { isValid: boolean; operation?: string }

  // State Events (from StateManager)
  'state:panel_opened': { panel: string; state: unknown }
  'state:panel_closed': { panel: string }
  'state:panel_updated': { panel: string; updates: unknown }
  'state:diagram_updated': { updates: unknown }
  'state:selection_changed': { selectedNodes: string[] }
  'state:voice_updated': { updates: unknown }
  'state:ui_updated': { updates: unknown }
  'state:reset': Record<string, never>
  'state:changed': { path: string; value: unknown }

  // Notification Events
  'notification:show': { message: string; type?: 'success' | 'error' | 'warning' | 'info' }
  'notification:show_requested': { message: string; type?: string }
  'notification:get_text': { key: string }
  'notification:text_retrieved': { key: string; text: string }
  'notification:play_sound_requested': Record<string, never>

  // Node Operations
  'node:add_requested': { parentId?: string; category?: string }
  'node:delete_requested': { nodeId: string }
  'node:empty_requested': { nodeId: string }
  'node:duplicate_requested': Record<string, never>
  'node:selected': { nodeId: string; nodeData?: unknown }
  'node:text_updated': { nodeId: string; text: string }
  'node:resized': { nodeId?: string }
  'node:edit_requested': { nodeId: string }

  // Canvas Events
  'canvas:fitted_with_panel': { panelWidth: number }
  'canvas:fitted_full': Record<string, never>
  'canvas:resized': { width: number; height: number }
  'canvas:fit_requested': { animate?: boolean }

  // Window Events
  'window:resized': { width: number; height: number }

  // Toolbar Events
  'toolbar:export_requested': { format: string }
  'toolbar:import_file': { file: File }

  // File Events
  'file:mg_export_completed': { filename: string }
  'file:mg_export_error': { error: string }

  // SSE Events
  'sse:stream_started': { url: string }
  'sse:stream_completed': { url: string }
  'sse:stream_aborted': { url: string }
  'sse:stream_error': { url: string; error: string }
  'sse:chunk_received': { chunk: string }

  // Properties Events
  'properties:apply_all_requested': Record<string, never>
  'properties:apply_realtime_requested': { property: string; value: unknown }
  'properties:reset_requested': Record<string, never>
  'properties:toggle_bold_requested': Record<string, never>
  'properties:toggle_italic_requested': Record<string, never>
  'properties:toggle_underline_requested': Record<string, never>
  'properties:toggle_strikethrough_requested': Record<string, never>

  // Text Events
  'text:apply_requested': { text: string }
  'toolbar:update_state_requested': { state: unknown }

  // Diagram Reset
  'diagram:reset_requested': Record<string, never>

  // Learning Mode Events
  'learning_mode:validate': { mode?: string }
  'learning_mode:validated': { result: unknown }
  'learning_mode:start_requested': Record<string, never>

  // Node Palette Events
  'node_palette:toggle_requested': Record<string, never>

  // Node Counter Events
  'node_counter:setup_observer': Record<string, never>
  'node_counter:update_requested': Record<string, never>

  // UI State LLM Events
  'ui:toggle_line_mode': Record<string, never>
  'ui:set_auto_button_loading': { loading: boolean }
  'ui:set_all_llm_buttons_loading': { loading: boolean }
  'ui:set_llm_button_state': { button: string; state: unknown }
  'llm:model_selection_clicked': Record<string, never>

  // MindMap specific
  'mindmap:layout_recalculation_requested': { source?: string }
  'mindmap:selection_restore_requested': { nodeIds: string[] }

  // Tab Mode Events
  'tab_mode:toggled': { enabled: boolean }
  'tab_mode:node_expanded': { nodeId: string }

  // Keyboard Events
  'keyboard:delete_executed': { deletedNodeIds?: string[]; nodeCount?: number; edgeCount?: number }
  'keyboard:escape_pressed': Record<string, never>
  'keyboard:select_all_executed': { selectedNodeIds?: string[]; nodeCount?: number }

  // Diagram Orientation
  'diagram:orientation_changed': { orientation: string }

  // Multi-Flow Map Events
  'multi_flow_map:topic_width_changed': { nodeId: string; width: number | null }
  'multi_flow_map:node_width_changed': { nodeId: string; width: number | null }

  // Wildcard for any event (for debugging)
  '*': { event: string; data: unknown }
}

// ============================================================================
// Types
// ============================================================================

type EventKey = keyof EventTypes
type EventHandler<K extends EventKey> = Handler<EventTypes[K]>
type WildcardHandler = (event: EventKey, data: unknown) => void

interface ListenerInfo {
  event: EventKey
  handler: EventHandler<EventKey>
}

interface EventStats {
  totalEvents: number
  uniqueEvents: number
  topEvents: Array<{ event: string; count: number }>
  totalListeners: number
  globalListeners: number
}

// ============================================================================
// Enhanced Event Bus Class
// ============================================================================

class EnhancedEventBus {
  private emitter: Emitter<EventTypes>
  private ownerRegistry: Map<string, ListenerInfo[]>
  private wildcardListeners: Set<WildcardHandler>
  private eventStats: Map<string, number>
  private debugMode: boolean
  private performanceThreshold: number

  constructor() {
    this.emitter = mitt<EventTypes>()
    this.ownerRegistry = new Map()
    this.wildcardListeners = new Set()
    this.eventStats = new Map()
    this.debugMode = false
    this.performanceThreshold = 100 // Warn if event takes > 100ms

    if (this.debugMode) {
      console.log('[EventBus] Enhanced Event Bus initialized')
    }
  }

  // ==========================================================================
  // Core Methods (delegated to mitt)
  // ==========================================================================

  /**
   * Subscribe to an event
   */
  on<K extends EventKey>(event: K, handler: EventHandler<K>): () => void {
    this.emitter.on(event, handler as Handler<EventTypes[K]>)

    if (this.debugMode) {
      console.log(`[EventBus] Listener added for: ${event}`)
    }

    return () => this.off(event, handler)
  }

  /**
   * Subscribe to an event once (auto-removes after first trigger)
   */
  once<K extends EventKey>(event: K, handler: EventHandler<K>): () => void {
    const onceHandler: EventHandler<K> = (data) => {
      this.off(event, onceHandler)
      handler(data)
    }

    return this.on(event, onceHandler)
  }

  /**
   * Unsubscribe from an event
   */
  off<K extends EventKey>(event: K, handler?: EventHandler<K>): void {
    if (handler) {
      this.emitter.off(event, handler as Handler<EventTypes[K]>)
    } else {
      this.emitter.off(event)
    }

    if (this.debugMode) {
      console.log(`[EventBus] Listener removed for: ${event}`)
    }
  }

  /**
   * Emit an event with data
   */
  emit<K extends EventKey>(event: K, data: EventTypes[K]): void {
    const startTime = performance.now()

    // Track event frequency
    this.eventStats.set(event, (this.eventStats.get(event) || 0) + 1)

    if (this.debugMode) {
      console.log(`[EventBus] Event emitted: ${event}`, data)
    }

    // Emit to regular listeners
    try {
      this.emitter.emit(event, data)
    } catch (error) {
      console.error(`[EventBus] Listener error for ${event}:`, error)
    }

    // Emit to wildcard listeners
    this.wildcardListeners.forEach((handler) => {
      try {
        handler(event, data)
      } catch (error) {
        console.error(`[EventBus] Wildcard handler error for ${event}:`, error)
      }
    })

    // Performance warning
    const duration = performance.now() - startTime
    if (duration > this.performanceThreshold) {
      console.warn(
        `[EventBus] Slow event: ${event} took ${duration.toFixed(2)}ms (threshold: ${this.performanceThreshold}ms)`
      )
    }
  }

  // ==========================================================================
  // Enhanced Methods (owner tracking)
  // ==========================================================================

  /**
   * Subscribe to an event with owner tracking for automatic cleanup
   */
  onWithOwner<K extends EventKey>(event: K, handler: EventHandler<K>, owner: string): () => void {
    if (!owner) {
      console.warn('[EventBus] onWithOwner called without owner - falling back to on()')
      return this.on(event, handler)
    }

    // Register listener normally
    this.on(event, handler)

    // Track ownership in registry
    if (!this.ownerRegistry.has(owner)) {
      this.ownerRegistry.set(owner, [])
    }
    const ownerListeners = this.ownerRegistry.get(owner)
    if (ownerListeners) {
      ownerListeners.push({
        event,
        handler: handler as EventHandler<EventKey>,
      })
    }

    if (this.debugMode) {
      console.log(`[EventBus] Listener added with owner: ${event} (owner: ${owner})`)
    }

    // Return unsubscribe function that removes from both places
    return () => {
      this.off(event, handler)
      this.removeFromRegistry(owner, event, handler as EventHandler<EventKey>)
    }
  }

  /**
   * Remove ALL listeners for an owner (automatic cleanup)
   */
  removeAllListenersForOwner(owner: string): number {
    const listeners = this.ownerRegistry.get(owner) || []

    if (listeners.length === 0) {
      return 0
    }

    // Remove each listener from Event Bus
    listeners.forEach(({ event, handler }) => {
      this.emitter.off(event, handler as Handler<EventTypes[typeof event]>)
    })

    // Remove from registry
    this.ownerRegistry.delete(owner)

    if (this.debugMode) {
      console.log(`[EventBus] Removed ${listeners.length} listeners for owner: ${owner}`)
    }

    return listeners.length
  }

  /**
   * Subscribe to all events (useful for debugging)
   */
  onAny(handler: WildcardHandler): () => void {
    this.wildcardListeners.add(handler)

    if (this.debugMode) {
      console.log(`[EventBus] Global listener added (total: ${this.wildcardListeners.size})`)
    }

    return () => this.offAny(handler)
  }

  /**
   * Remove global listener
   */
  offAny(handler: WildcardHandler): void {
    this.wildcardListeners.delete(handler)
  }

  // ==========================================================================
  // Utility Methods
  // ==========================================================================

  /**
   * Remove all listeners for an event (or all events)
   */
  clear(event?: EventKey): void {
    if (event) {
      this.emitter.off(event)
    } else {
      this.emitter.all.clear()
      this.wildcardListeners.clear()
      this.ownerRegistry.clear()
    }
  }

  /**
   * Check if event has listeners
   */
  hasListeners(event: EventKey): boolean {
    const handlers = this.emitter.all.get(event)
    return (handlers && handlers.length > 0) || this.wildcardListeners.size > 0
  }

  // ==========================================================================
  // Debug Methods
  // ==========================================================================

  /**
   * Get event statistics
   */
  getStats(): EventStats {
    const totalEvents = Array.from(this.eventStats.values()).reduce((a, b) => a + b, 0)
    const uniqueEvents = this.eventStats.size
    const topEvents = Array.from(this.eventStats.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([event, count]) => ({ event, count }))

    let totalListeners = 0
    this.emitter.all.forEach((handlers) => {
      totalListeners += handlers.length
    })

    return {
      totalEvents,
      uniqueEvents,
      topEvents,
      totalListeners,
      globalListeners: this.wildcardListeners.size,
    }
  }

  /**
   * Get all registered event names
   */
  getEventNames(): string[] {
    return Array.from(this.emitter.all.keys()).sort()
  }

  /**
   * Get listeners for a specific owner
   */
  getListenersForOwner(owner: string): ListenerInfo[] {
    return this.ownerRegistry.get(owner) || []
  }

  /**
   * Get all listeners grouped by owner
   */
  getAllListeners(): Record<string, Array<{ event: EventKey }>> {
    const result: Record<string, Array<{ event: EventKey }>> = {}
    this.ownerRegistry.forEach((listeners, owner) => {
      result[owner] = listeners.map((l) => ({ event: l.event }))
    })
    return result
  }

  /**
   * Get listener count by owner
   */
  getListenerCounts(): Record<string, number> {
    const counts: Record<string, number> = {}
    this.ownerRegistry.forEach((listeners, owner) => {
      counts[owner] = listeners.length
    })
    return counts
  }

  /**
   * Enable/disable debug mode
   */
  setDebugMode(enabled: boolean): void {
    this.debugMode = enabled
    console.log(`[EventBus] Debug mode ${enabled ? 'enabled' : 'disabled'}`)
  }

  /**
   * Set performance threshold
   */
  setPerformanceThreshold(ms: number): void {
    this.performanceThreshold = ms
  }

  // ==========================================================================
  // Private Helpers
  // ==========================================================================

  private removeFromRegistry(
    owner: string,
    event: EventKey,
    handler: EventHandler<EventKey>
  ): void {
    const ownerListeners = this.ownerRegistry.get(owner)
    if (!ownerListeners) return

    const index = ownerListeners.findIndex(
      (item) => item.event === event && item.handler === handler
    )
    if (index > -1) {
      ownerListeners.splice(index, 1)
    }

    // Clean up empty owner entries
    if (ownerListeners.length === 0) {
      this.ownerRegistry.delete(owner)
    }
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

const eventBus = new EnhancedEventBus()

// Expose debug tools on window in development
if (typeof window !== 'undefined' && import.meta.env.DEV) {
  ;(window as unknown as Record<string, unknown>).debugEventBus = {
    stats: () => eventBus.getStats(),
    events: () => eventBus.getEventNames(),
    listeners: (owner?: string) =>
      owner ? eventBus.getListenersForOwner(owner) : eventBus.getAllListeners(),
    counts: () => eventBus.getListenerCounts(),
    removeOwner: (owner: string) => eventBus.removeAllListenersForOwner(owner),
    debug: (enabled: boolean) => eventBus.setDebugMode(enabled),
    clear: (event?: EventKey) => eventBus.clear(event),
  }

  console.log('%c[EventBus] Debug tools available:', 'color: #4caf50; font-weight: bold;')
  console.log('  window.debugEventBus.stats()  - View event statistics')
  console.log('  window.debugEventBus.events() - List all event names')
  console.log('  window.debugEventBus.listeners() - List all listeners by owner')
  console.log('  window.debugEventBus.listeners("Owner") - List listeners for specific owner')
  console.log('  window.debugEventBus.counts() - Get listener counts by owner')
  console.log('  window.debugEventBus.removeOwner("Owner") - Remove all listeners for owner')
  console.log('  window.debugEventBus.debug(true/false) - Toggle debug mode')
}

// ============================================================================
// Vue Composable
// ============================================================================

/**
 * Event Bus composable with automatic cleanup on component unmount
 */
export function useEventBus(owner?: string) {
  const unsubscribers: (() => void)[] = []
  const composableOwner = owner || `component_${Date.now()}_${Math.random().toString(36).slice(2)}`

  /**
   * Subscribe to an event (auto-cleanup on unmount)
   */
  function on<K extends EventKey>(event: K, handler: EventHandler<K>): () => void {
    const unsubscribe = eventBus.onWithOwner(event, handler, composableOwner)
    unsubscribers.push(unsubscribe)
    return unsubscribe
  }

  /**
   * Subscribe to an event once (auto-cleanup on unmount)
   */
  function once<K extends EventKey>(event: K, handler: EventHandler<K>): () => void {
    const onceHandler: EventHandler<K> = (data) => {
      off(event, onceHandler)
      handler(data)
    }
    return on(event, onceHandler)
  }

  /**
   * Emit an event
   */
  function emit<K extends EventKey>(event: K, data: EventTypes[K]): void {
    eventBus.emit(event, data)
  }

  /**
   * Unsubscribe from an event
   */
  function off<K extends EventKey>(event: K, handler?: EventHandler<K>): void {
    eventBus.off(event, handler)
  }

  /**
   * Subscribe to all events (auto-cleanup on unmount)
   */
  function onAny(handler: WildcardHandler): () => void {
    const unsubscribe = eventBus.onAny(handler)
    unsubscribers.push(unsubscribe)
    return unsubscribe
  }

  // Cleanup on component unmount
  onUnmounted(() => {
    // First call individual unsubscribers
    unsubscribers.forEach((unsub) => unsub())
    unsubscribers.length = 0

    // Then remove any remaining listeners for this owner
    eventBus.removeAllListenersForOwner(composableOwner)
  })

  return {
    on,
    once,
    emit,
    off,
    onAny,
    offAny: eventBus.offAny.bind(eventBus),
    clear: eventBus.clear.bind(eventBus),
    hasListeners: eventBus.hasListeners.bind(eventBus),
    // Debug methods
    getStats: eventBus.getStats.bind(eventBus),
    getEventNames: eventBus.getEventNames.bind(eventBus),
    getListenerCounts: eventBus.getListenerCounts.bind(eventBus),
  }
}

// ============================================================================
// Direct Access (for use outside components)
// ============================================================================

export { eventBus }

// Re-export types for consumers
export type { EventKey, EventHandler, WildcardHandler, EventStats }
