/**
 * Shared types for workshop / canvas-collab WebSocket composables.
 */

export interface ParticipantInfo {
  user_id: number
  username: string
}

export type ConnectionStatus = 'connected' | 'reconnecting' | 'failed'

export type WorkshopRole = 'host' | 'editor' | 'viewer'

export interface WorkshopUpdate {
  type:
    | 'update'
    | 'update_ack'
    | 'user_joined'
    | 'user_left'
    | 'joined'
    | 'snapshot'
    | 'error'
    | 'pong'
    | 'node_editing'
    | 'node_editing_batch'
    | 'node_editing_batch_ws'
    | 'node_selected'
    | 'resync'
    | 'room_idle_warning'
    | 'kicked'
    | 'role_changed'
    | 'role_change_ack'
    | 'write_locked'
    | 'claim_node_edit'
    | 'node_edit_claimed'
  diagram_id?: string
  spec?: Record<string, unknown>
  nodes?: Array<Record<string, unknown>>
  connections?: Array<Record<string, unknown>>
  deleted_node_ids?: string[]
  deleted_connection_ids?: string[]
  user_id?: number
  username?: string
  timestamp?: string
  participants?: number[]
  participants_with_names?: ParticipantInfo[]
  message?: string
  node_id?: string
  /** Batch lock/unlock: list of node IDs from `node_editing_batch` server broadcast. */
  node_ids?: string[]
  editing?: boolean
  color?: string
  emoji?: string
  selected?: boolean
  owner_id?: number
  version?: number
  seq?: number
  role?: WorkshopRole
  workshop_visibility?: string
  idle_deadline_unix?: number
  grace_seconds_remaining?: number
  reason?: string
  promoted_by?: number
  demoted_by?: number
  to?: WorkshopRole
  /** Structured error discriminator (e.g. collab ``update_rejected``). */
  code?: string
  /** Client-assigned id on ``update`` / echoed on ``update_ack`` for queue dedupe. */
  client_op_id?: string
  /** Server echo: node patches dropped by lock filter (``update_partial_filtered``). */
  filtered_node_ids?: string[]
  /** True while a participant's write is in progress; false when the lock is released. */
  locked?: boolean
  events?: NodeEditingEvent[]
  /** Short-lived reconnect bypass for Redis join sliding windows (`?resume=`). */
  resume_token?: string
  /** Correlation id for ``update`` / ``update_ack`` tracing (server-generated). */
  ws_msg_id?: string
  /** Persisted diagram title from joined payload for session banners. */
  diagram_title?: string
  /** node_edit_claimed: whether the claim was granted (true) or denied (false). */
  granted?: boolean
  /** node_edit_claimed denied: username of the participant who holds the lock. */
  held_by_username?: string
  /** node_edit_claimed denied: user_id of the participant who holds the lock. */
  held_by_user_id?: number
}

export interface RemoteNodeSelection {
  nodeId: string
  username: string
  color: string
}

export interface ActiveEditor {
  user_id: number
  username: string
  color: string
  emoji: string
}

/** Single event inside a `node_editing_batch_ws` frame (server mirrors `node_editing`). */
export interface NodeEditingEvent {
  type: 'node_editing'
  node_id: string
  editing?: boolean
  user_id?: number
  username?: string
  color?: string
  emoji?: string
}
