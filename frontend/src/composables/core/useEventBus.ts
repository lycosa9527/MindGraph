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

import type { CanvasExportOptions } from '@/config/canvasExportOptions'

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
  'nodePalette:opened': {
    diagramKey?: string
    hasRestoredSession: boolean
    /** True when panel was already open and we switched to a new node tab (concept generation) */
    wasPanelAlreadyOpen?: boolean
  }
  /** Stop all node-palette SSE requests (e.g. panel closed or canvas exited). */
  'node_palette:streaming_stop_requested': Record<string, never>
  'concept_parking_lot:opened': {
    diagramKey?: string
    hasRestoredSession: boolean
  }
  /** Stop concept parking lot SSE requests (panel closed or canvas exited). */
  'concept_parking_lot:streaming_stop_requested': Record<string, never>

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
  'diagram:collab_delete_blocked': Record<string, never>
  'diagram:add_node_requested': Record<string, never>
  'diagram:add_branch_requested': Record<string, never>
  'diagram:add_child_requested': Record<string, never>
  'diagram:add_sibling_requested': Record<string, never>
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
  'diagram:auto_complete_branch_requested': {
    source?: string
    nodeId?: string
    nodeLabel?: string
  }
  'diagram:position_saved': {
    nodeId: string
    position: { x: number; y: number }
    diagramType?: string
  }
  'diagram:positions_cleared': { diagramType?: string }
  'diagram:position_changed': {
    nodeId: string
    position: { x: number; y: number }
    isCustom?: boolean
  }
  'diagram:style_changed': { nodeId?: string; style?: unknown; all?: boolean; preset?: boolean }
  'diagram:learning_sheet_changed': Record<string, never>
  'diagram:loaded': { diagramType: string; spec?: unknown }
  'diagram:loaded_from_library': { diagramId: string; diagramType: string }
  'diagram:double_bubble_relayout_requested': Record<string, never>
  /** Increment diagram store layoutRecalcTrigger (e.g. after lazy-loaded KaTeX/markdown pipeline). */
  'diagram:layout_recalc_bump': Record<string, never>
  'diagram:branch_moved': Record<string, never>
  'mindmap:canvas_mode_changed': {
    previousMode: 'legacy' | 'v2'
    newMode: 'legacy' | 'v2'
  }
  'snapshot:requested': Record<string, never>
  'diagram:workshop_snapshot_applied': Record<string, never>
  'concept_map:link_drop': { sourceId: string; targetId: string; linkedFromConnectionId?: string }
  /**
   * Link handle (node menu or relationship menu): start drawing a link. Uses Pointer events so
   * touch/mouse/pen share one path; `pointerdown` on the handle must be `.capture` + `stopPropagation`
   * so the node body keeps normal node drag. Followed by window-level pointer move/up in the canvas composable.
   */
  'concept_map:link_handle_pointer_start': {
    pointerId: number
    clientX: number
    clientY: number
    sourceId?: string
    connectionId?: string
    labelX?: number
    labelY?: number
    relSource?: string
    relTarget?: string
  }
  'concept_map:link_drag_end': Record<string, never>
  'concept_map:label_cleared': {
    connectionId: string
    sourceId: string
    targetId: string
  }
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
  'voice:assistant_text_done': { text: string }
  'voice:action_executed': { action: string; params?: unknown }
  'voice:diagram_update_executed': {
    action: string
    updates?: unknown
    summary?: string
    userSummary?: string
    verified?: boolean
    errorCode?: string
  }
  'voice:context_mutation_ack': {
    ok?: boolean
    revision?: number
    library_snapshot_saved?: boolean
    library_snapshot_error?: string
    idempotency_key?: string
    persist_library?: boolean
    error?: string
  }
  'voice:error': { error: string }
  'voice:destroyed': Record<string, never>
  'voice:cleanup_started': { diagramSessionId?: string }
  'voice:cleanup_backend_requested': { diagramSessionId?: string }
  'voice:cleanup_backend_completed': { diagramSessionId?: string }
  'voice:cleanup_backend_failed': { diagramSessionId?: string; error?: string }
  'voice:server_error': { error: string; code?: string }
  'voice:debug_rx': {
    ts: number
    direction: 'in'
    type: string
    line: string
  }
  'kitty:asr_partial': { text: string; utteranceId?: string }
  'kitty:asr_final': { text: string; utteranceId?: string }
  'kitty:asr_started': { utteranceId?: string }
  'kitty:asr_stopped': { utteranceId?: string; text?: string }
  /** Inbound diagram mutation — single apply path owns Pinia + Hub persist. */
  'kitty:diagram_mutation_requested': {
    action: string
    updates: Record<string, unknown>
    mutationId?: string
    userSummary?: string
    expectedEffect?: import('@/utils/diagramEditVerify').DiagramEditExpectedEffect
    beforeFingerprint?: {
      nodes: import('@/types').DiagramNode[]
      connections: import('@/types').Connection[]
    }
    sendAck?: (payload: Record<string, unknown>) => void
    hubPersist?: {
      buildContext: () => import('@/composables/kitty/kittyAgentTypes').KittyAgentContext
      updateContext: (
        context: import('@/composables/kitty/kittyAgentTypes').KittyAgentContext,
        options?: import('@/composables/kitty/kittyAgentTypes').KittyContextUpdateOptions
      ) => void
      scope?: string | null
    }
    lane?: 'mobile' | 'desktop'
  }
  'kitty:inline_recommendations_requested': { nodeId?: string; nodeIndex?: number }
  'kitty:add_node_with_recommendations_requested': { text?: string }
  'kitty:desktop_diagram_update': {
    scope?: string
    action?: string
    updates?: unknown
    mutation_id?: string
  }
  'kitty:desktop_selection_update': {
    scope?: string
    selected_nodes?: string[]
  }
  'kitty:desktop_llm_model_update': {
    scope?: string
    selected_llm_model?: string | null
  }
  'kitty:desktop_voice_command': {
    scope?: string
    action?: string
    detail?: string
  }
  'kitty:desktop_voice_phase_update': {
    scope?: string
    phase?: string
  }
  'kitty:workflow_trace': {
    lane: 'mobile' | 'desktop' | 'hub'
    stage: string
    detail: string
    scope?: string
    action?: string
    at: number
  }
  'kitty:diagram_review_annotation': {
    summary: string
    items: Array<{ node_id: string; reason: string; suggestion?: string }>
  }
  /** Owning tab finished Hub persist from Pinia; observers may recover, owner must not. */
  'kitty:hub_diagram_persisted': {
    scope: string
    revision?: number
    source?: 'owning_tab' | 'observer'
  }
  'kitty:diagram_edit_failed': {
    action: string
    errorCode: string
    message?: string
    scope?: string | null
  }
  /** Chat reply lane — decoupled from diagram mutations. */
  'kitty:one_sentence_reply': {
    text: string
    kind: 'progress' | 'final' | 'conversational'
    action?: string
    choices?: Array<{ index: number; label: string }>
    requestId?: string
  }

  // One-sentence mini-chat (Pinia SoT + cooperators)
  'oneSentence:request_queued': {
    requestId: string
    status: 'queued'
    text?: string
    scope?: string
  }
  'oneSentence:request_inflight': {
    requestId: string
    status: 'inflight'
    text?: string
    scope?: string
  }
  'oneSentence:request_done': {
    requestId: string
    status: 'done'
    text?: string
    scope?: string
  }
  'oneSentence:request_failed': {
    requestId: string
    status: 'failed'
    text?: string
    errorCode?: string
    scope?: string
  }
  'oneSentence:session_ready': { scope: string }
  'oneSentence:session_migrated': { fromScope: string; toScope: string }
  'oneSentence:session_reset': { scope: string }
  'oneSentence:messages_changed': { scope?: string }
  /** Async canvas action finished (e.g. branch subgraph LLM). */
  'kitty:diagram_action_completed': {
    action: string
    ok: boolean
    userSummary?: string
    errorCode?: string
  }

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
  'view:fit_to_window_requested': {
    animate?: boolean
    /** Allowed to run on desktop concept map (toolbar / explicit user action). */
    userInitiated?: boolean
    /** Server/export framing (e.g. ExportRenderPage). */
    forExport?: boolean
  }
  'view:fit_to_canvas_requested': {
    animate?: boolean
    userInitiated?: boolean
    forExport?: boolean
  }
  'view:fit_to_nodes_requested': {
    nodeIds: string[]
    animate?: boolean
    duration?: number
    padding?: number
    userInitiated?: boolean
  }
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

  /** Canvas presentation rail: Ctrl/Cmd+6 toggles virtual keyboard */
  'presentation:toggle_virtual_keyboard_requested': Record<string, never>

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
  'node_editor:tab_pressed': { nodeId: string; draftText?: string }
  /** Insert snippet into active label editor at caret, or toolbar falls back to appending to node text */
  'node_editor:insert_text': { nodeId: string; snippet: string }
  /** Fired when InlineEditableText applied insert at caret (toolbar skips store append) */
  'node_editor:insert_text_consumed': { nodeId: string }
  /** Insert a manual line break at the caret in the active label editor */
  'node_editor:insert_line_break': { nodeId: string }

  // Workshop Events
  'workshop:code-changed': {
    code: string | null
    visibility?: 'organization' | 'network' | null
  }
  'workshop:role-changed': {
    userId?: number
    role: string
  }
  'workshop:host-started': Record<string, never>
  /** Emitted when another participant acquires (locked=true) or releases (locked=false) the room write lock. */
  'workshop:write-locked': { userId: number; locked: boolean }
  /** Emitted when the server acks a sent update; carries the set of node ids that were in that op. */
  'workshop:collab-ack': { nodeIds: string[] }
  /** Emitted when a subset of node patches were silently dropped by the server's lock filter. */
  'workshop:partial-filtered': { nodeIds: string[] }
  /** Emitted when the server denies a node_edit claim because another user holds the lock. */
  'workshop:node-edit-denied': { nodeId: string; heldByUsername: string }

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
  /** Fired after an interactive sign-in (password, SMS, passkey, OAuth), not session restore. */
  'auth:login_success': Record<string, never>

  // MindMate Events
  'mindmate:opened': { diagramSessionId?: string }
  'mindmate:closed': Record<string, never>
  'mindmate:send_message': { message: string }
  'mindmate:message_sending': { message: string; files?: unknown[] }
  'mindmate:load_phase': { phase: string }
  'mindmate:message_chunk': { chunk: string }
  'mindmate:message_completed': { conversationId?: string }
  'mindmate:error': { error: string }
  'mindmate:stream_error': { error: string | undefined; error_type?: string; message?: string }
  'thinking_coins:insufficient': Record<string, never>
  'thinking_coins:focus_school': Record<string, never>
  'thinking_coins:mutation': import('@/types/thinkingCoins').ThinkingCoinMutationPayload
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
  'llm:model_completed': { model?: string; success?: boolean; rendered?: boolean }
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
  'inline_recommendation:applied': { nodeId: string; text: string; appliedToConnectionId?: string }

  // Canvas Events
  'canvas:pane_clicked': Record<string, never>
  'canvas:fitted_with_panel': { panelWidth: number }
  'canvas:fitted_full': Record<string, never>
  'canvas:resized': { width: number; height: number }
  'canvas:fit_requested': { animate?: boolean }
  'canvas:show_slot_full_modal': Record<string, never>

  // Window Events
  'window:resized': { width: number; height: number }

  // Toolbar Events
  'toolbar:export_requested': { format: string; options?: CanvasExportOptions }
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
  'diagram:history_restored': { diagramType?: string }

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

  // Keyboard Events
  'keyboard:delete_executed': { deletedNodeIds?: string[]; nodeCount?: number; edgeCount?: number }
  'keyboard:escape_pressed': Record<string, never>
  'keyboard:select_all_executed': { selectedNodeIds?: string[]; nodeCount?: number }

  // Diagram Orientation
  'diagram:orientation_changed': { orientation: string }

  // Multi-Flow Map Events
  'multi_flow_map:topic_width_changed': { nodeId: string; width: number | null }
  'multi_flow_map:node_width_changed': { nodeId: string; width: number | null }

  // Admin Panel Events
  'admin:tab_activated': { tab: string; subtab?: string; view?: string }
  'admin:org_selected': { orgId: number | null }
  'admin:refresh_requested': { domain: string }
  'admin:mutation_completed': { domain: string; entityId?: number | string }
  'admin:toolbar_action': { action: string; tab: string; payload?: Record<string, unknown> }

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
      if (import.meta.env.DEV) {
        console.error(`[EventBus] Listener error for ${event}:`, error)
      }
    }

    // Emit to wildcard listeners
    this.wildcardListeners.forEach((handler) => {
      try {
        handler(event, data)
      } catch (error) {
        if (import.meta.env.DEV) {
          console.error(`[EventBus] Wildcard handler error for ${event}:`, error)
        }
      }
    })

    // Performance warning
    const duration = performance.now() - startTime
    if (import.meta.env.DEV && duration > this.performanceThreshold) {
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
      if (import.meta.env.DEV) {
        console.warn('[EventBus] onWithOwner called without owner - falling back to on()')
      }
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
    if (import.meta.env.DEV) {
      console.log(`[EventBus] Debug mode ${enabled ? 'enabled' : 'disabled'}`)
    }
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
