/**
 * WebSocket `onmessage` dispatch for canvas-collab workshop protocol.
 */
import type { Ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import type {
  ActiveEditor,
  NodeEditingEvent,
  ParticipantInfo,
  RemoteNodeSelection,
  WorkshopRole,
  WorkshopUpdate,
} from '@/composables/workshop/useWorkshopTypes'

import type { CollabSyncVersion } from './useCollabSyncVersion'

// applySnapshotFrame / evaluateLiveSpecGap are now used inside useCollabSyncVersion;
// they are intentionally NOT imported here any more.

/** Same as `useLanguage().t` (workshop passes that into message deps). */
export type WorkshopMessageTranslateFn = UseLanguageTranslate

export interface WorkshopMessageNotifyFns {
  error: (message: string) => void
  warning: (message: string) => void
  info: (message: string) => void
}

export interface WorkshopAuthContext {
  getCurrentUserIdString: () => string
}

/** After this many successive stale live-spec frames, force a ``resync`` (Redis re-seed). */
export const WORKSHOP_STALE_RESYNC_THRESHOLD = 5

export interface WorkshopMutableSessionState {
  /** Diagram ID for the current workshop session (set from server ``joined``). */
  sessionDiagramId: string | null
}

export interface WorkshopMessageDispatchDeps {
  workshopCode: Ref<string | null>
  diagramId: Ref<string | null>
  mutable: WorkshopMutableSessionState
  /** Reactive version / sequencing state (replaces the old cursor fields on ``mutable``). */
  version: CollabSyncVersion
  participants: Ref<number[]>
  participantsWithNames: Ref<ParticipantInfo[]>
  workshopRole: Ref<WorkshopRole>
  diagramOwnerId: Ref<number | null>
  activeEditors: Ref<Map<string, ActiveEditor>>
  remoteSelectionsByUser: Ref<Map<number, RemoteNodeSelection>>
  joinResumeToken: Ref<string | null>
  sessionDiagramTitle: Ref<string | null>
  auth: WorkshopAuthContext
  onUpdate?: (spec: Record<string, unknown>) => void
  onGranularUpdate?: (
    nodes?: Array<Record<string, unknown>>,
    connections?: Array<Record<string, unknown>>,
    deletedNodeIds?: string[],
    deletedConnectionIds?: string[]
  ) => void
  onNodeEditing?: (nodeId: string, editor: ActiveEditor | null) => void
  onServerSnapshot?: (spec: Record<string, unknown>, version: number) => void
  clearRoomIdleCountdownUi: () => void
  applyRoomIdleWarningFromServer: (payload: WorkshopUpdate) => void
  schedulePresenceNotification: (type: 'joined' | 'left', username: string) => void
  clearPendingResyncWatchdog: () => void
  schedulePendingResyncWatchdog: (sock: WebSocket) => void
  /** Replays deferred `sendUpdate` ops when WS is open and ready to flush. */
  flushOutboundQueue: () => void
  /** Marks the initial server baseline as applied for this socket generation. */
  markServerBaselineReady: () => void
  /** Outbound-queue ack hook for ``update_ack`` (may be legacy without id). */
  acknowledgeOutboundUpdate: (clientOpId?: string | null) => void
  /** Clears the half-open ``pong`` watchdog (call on ``pong`` message). */
  recordTransportPong: () => void
  /**
   * Node IDs affected by the op about to be acked (call **before**
   * ``acknowledgeOutboundUpdate`` dequeue).
   */
  collectAcknowledgedNodeIds: (clientOpId: string | null) => string[]
  notify: WorkshopMessageNotifyFns
  t: WorkshopMessageTranslateFn
  /**
   * Collaboration guest only: fired as soon as a terminating ``kicked`` frame
   * arrives so the UI can navigate before the socket ``close`` handshake finishes.
   */
  onGuestForcedExit?: (payload: { reason?: string }) => void
}

const GUEST_FORCED_EXIT_KICK_REASONS = new Set([
  'session_ended',
  'replaced_by_new_session',
  'room_idle',
])

function workshopGuestEligibleForForcedExit(deps: WorkshopMessageDispatchDeps): boolean {
  if (!deps.workshopCode.value) {
    return false
  }
  const oid = deps.diagramOwnerId.value
  if (oid == null) {
    return false
  }
  return deps.auth.getCurrentUserIdString() !== String(oid)
}

function normalizeBatchEditingEvent(raw: unknown): NodeEditingEvent | null {
  if (!raw || typeof raw !== 'object') {
    return null
  }
  const rec = raw as Record<string, unknown>
  if (rec.type !== 'node_editing' || typeof rec.node_id !== 'string') {
    return null
  }
  return raw as NodeEditingEvent
}

function looksLikePlaceholderEditorName(name: string, userId: number): boolean {
  const trimmed = name.trim()
  if (!trimmed) {
    return true
  }
  if (trimmed === String(userId)) {
    return true
  }
  if (/^\d+$/.test(trimmed)) {
    return true
  }
  if (new RegExp(`^User\\s+${userId}$`, 'i').test(trimmed)) {
    return true
  }
  return false
}

function resolveWorkshopEditorDisplayName(
  deps: WorkshopMessageDispatchDeps,
  userId: number,
  messageUsername?: string
): string {
  const fromMessage = messageUsername?.trim()
  if (fromMessage && !looksLikePlaceholderEditorName(fromMessage, userId)) {
    return fromMessage
  }
  const rosterEntry = deps.participantsWithNames.value.find((p) => p.user_id === userId)
  const fromRoster = rosterEntry?.username?.trim()
  if (fromRoster && !looksLikePlaceholderEditorName(fromRoster, userId)) {
    return fromRoster
  }
  return deps.t('workshopCanvas.collabEditorDisplayNameFallback')
}

export function dispatchWorkshopMessage(
  message: WorkshopUpdate,
  socket: WebSocket,
  deps: WorkshopMessageDispatchDeps
): void {
  switch (message.type) {
    case 'joined': {
      deps.clearRoomIdleCountdownUi()
      deps.participants.value = message.participants || []
      deps.participantsWithNames.value = message.participants_with_names || []
      if (message.owner_id !== undefined && message.owner_id !== null) {
        deps.diagramOwnerId.value = Number(message.owner_id)
      }
      if (message.role) {
        deps.workshopRole.value = message.role
      }
      if (message.diagram_id) {
        deps.mutable.sessionDiagramId = message.diagram_id
      }
      {
        const rawTitle =
          typeof message.diagram_title === 'string' ? message.diagram_title.trim() : ''
        deps.sessionDiagramTitle.value = rawTitle || null
      }
      const resumeTok = typeof message.resume_token === 'string' ? message.resume_token.trim() : ''
      deps.joinResumeToken.value = resumeTok || null
      if (
        deps.workshopCode.value &&
        (message.workshop_visibility === 'organization' ||
          message.workshop_visibility === 'network')
      ) {
        eventBus.emit('workshop:code-changed', {
          code: deps.workshopCode.value,
          visibility: message.workshop_visibility,
        })
      }
      deps.flushOutboundQueue()
      break
    }

    case 'snapshot': {
      deps.version.setPendingResync(false)
      deps.version.recordSnapshot(message.version, message.seq)
      if (!deps.version.pendingResync.value) {
        deps.clearPendingResyncWatchdog()
      }
      if (message.spec && deps.onServerSnapshot) {
        deps.onServerSnapshot(message.spec, message.version ?? 1)
        deps.markServerBaselineReady()
        deps.flushOutboundQueue()
      } else if (import.meta.env.DEV) {
        console.warn('[WorkshopWS] snapshot missing spec handler or spec payload; baseline not ready')
      }
      break
    }

    case 'update': {
      if (import.meta.env.DEV) {
        console.log('[CollabSync] update received', {
          user_id: message.user_id,
          version: message.version,
          seq: message.seq,
          liveVersion: deps.version.liveVersion.value,
          liveSeq: deps.version.liveSeq.value,
          pendingResync: deps.version.pendingResync.value,
          role: deps.workshopRole.value,
        })
      }
      if (deps.version.pendingResync.value) {
        if (import.meta.env.DEV) {
          console.warn('[CollabSync] update DROPPED reason=pending_resync')
        }
        break
      }
      const resyncDiagramId = deps.mutable.sessionDiagramId ?? deps.diagramId.value
      const result = deps.version.recordUpdate(message.version, message.seq)

      if (result.gap) {
        if (import.meta.env.DEV) {
          console.warn('[CollabSync] update DROPPED reason=seq_gap — requesting resync', {
            version: message.version,
            seq: message.seq,
          })
        }
        // Always mark pendingResync so future updates are consistently dropped
        // until a snapshot clears it. If the socket is not open right now the
        // next reconnect delivers a fresh snapshot which clears the flag.
        if (!deps.version.pendingResync.value) {
          deps.version.setPendingResync(true)
          deps.schedulePendingResyncWatchdog(socket)
        }
        if (resyncDiagramId && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: 'resync', diagram_id: resyncDiagramId }))
        }
        break
      }

      if (result.stale) {
        if (import.meta.env.DEV) {
          console.warn('[CollabSync] update DROPPED reason=stale', {
            version: message.version,
            seq: message.seq,
            consecutive: deps.version.consecutiveStale.value,
          })
        }
        if (result.consecutiveStaleHit && resyncDiagramId && socket.readyState === WebSocket.OPEN) {
          deps.version.setPendingResync(true)
          deps.schedulePendingResyncWatchdog(socket)
          socket.send(JSON.stringify({ type: 'resync', diagram_id: resyncDiagramId }))
        }
        break
      }

      // Frame accepted.
      deps.clearRoomIdleCountdownUi()
      const hasGranular =
        message.nodes !== undefined ||
        message.connections !== undefined ||
        (message.deleted_node_ids && message.deleted_node_ids.length > 0) ||
        (message.deleted_connection_ids && message.deleted_connection_ids.length > 0)
      if (import.meta.env.DEV) {
        console.log('[CollabSync] update ACCEPTED', {
          version: message.version,
          seq: message.seq,
          hasGranular,
          nodes: message.nodes?.length ?? 0,
          conns: message.connections?.length ?? 0,
          delNodes: message.deleted_node_ids?.length ?? 0,
          delConns: message.deleted_connection_ids?.length ?? 0,
        })
      }
      if (hasGranular) {
        if (deps.onGranularUpdate) {
          deps.onGranularUpdate(
            message.nodes,
            message.connections,
            message.deleted_node_ids,
            message.deleted_connection_ids
          )
        } else if (deps.onUpdate) {
          if (import.meta.env.DEV) {
            console.warn('[WorkshopWS] Granular update received but no onGranularUpdate handler')
          }
        }
      } else if (message.spec && deps.onUpdate) {
        deps.onUpdate(message.spec)
      }
      break
    }

    case 'node_editing':
      if (message.node_id) {
        if (message.editing && message.user_id && message.color && message.emoji) {
          const editor: ActiveEditor = {
            user_id: message.user_id,
            username: resolveWorkshopEditorDisplayName(deps, message.user_id, message.username),
            color: message.color,
            emoji: message.emoji,
          }
          deps.activeEditors.value.set(message.node_id, editor)

          if (deps.onNodeEditing) {
            deps.onNodeEditing(message.node_id, editor)
          }
        } else {
          deps.activeEditors.value.delete(message.node_id)

          if (deps.onNodeEditing) {
            deps.onNodeEditing(message.node_id, null)
          }
        }
      }
      break

    case 'user_joined': {
      const joinedId = message.user_id
      if (joinedId == null) {
        break
      }
      if (!deps.participants.value.includes(joinedId)) {
        deps.participants.value.push(joinedId)
      }
      if (!deps.participantsWithNames.value.some((p) => p.user_id === joinedId)) {
        deps.participantsWithNames.value.push({
          user_id: joinedId,
          username: message.username || `User ${joinedId}`,
        })
      }
      deps.schedulePresenceNotification('joined', message.username || String(joinedId))
      break
    }

    case 'user_left': {
      const leftId = message.user_id
      const leftUsername =
        deps.participantsWithNames.value.find((p) => p.user_id === leftId)?.username ||
        message.username ||
        String(leftId)
      const pIdx = deps.participants.value.indexOf(leftId as number)
      if (pIdx !== -1) {
        deps.participants.value.splice(pIdx, 1)
      }
      const pnIdx = deps.participantsWithNames.value.findIndex((p) => p.user_id === leftId)
      if (pnIdx !== -1) {
        deps.participantsWithNames.value.splice(pnIdx, 1)
      }
      if (leftId != null) {
        deps.remoteSelectionsByUser.value.delete(leftId)
        deps.remoteSelectionsByUser.value = new Map(deps.remoteSelectionsByUser.value)
      }
      deps.schedulePresenceNotification('left', leftUsername)
      break
    }

    case 'node_selected': {
      const uid = message.user_id
      const nid = message.node_id
      if (uid == null || !nid) {
        break
      }
      if (String(uid) === deps.auth.getCurrentUserIdString()) {
        break
      }
      if (message.selected === false) {
        deps.remoteSelectionsByUser.value.delete(uid)
      } else {
        deps.remoteSelectionsByUser.value.set(uid, {
          nodeId: nid,
          username: message.username || `User ${uid}`,
          color: message.color || '#f97316',
        })
      }
      deps.remoteSelectionsByUser.value = new Map(deps.remoteSelectionsByUser.value)
      break
    }

    case 'node_editing_batch': {
      const nodeIds = Array.isArray(message.node_ids) ? message.node_ids : []
      if (message.editing && message.user_id && message.color && message.emoji) {
        const editor: ActiveEditor = {
          user_id: message.user_id,
          username: resolveWorkshopEditorDisplayName(deps, message.user_id, message.username),
          color: message.color,
          emoji: message.emoji,
        }
        for (const nid of nodeIds) {
          if (!nid) continue
          deps.activeEditors.value.set(nid, editor)
          if (deps.onNodeEditing) {
            deps.onNodeEditing(nid, editor)
          }
        }
      } else {
        for (const nid of nodeIds) {
          if (!nid) continue
          deps.activeEditors.value.delete(nid)
          if (deps.onNodeEditing) {
            deps.onNodeEditing(nid, null)
          }
        }
      }
      break
    }

    case 'node_editing_batch_ws': {
      const events = Array.isArray(message.events) ? message.events : []
      for (const raw of events) {
        const evt = normalizeBatchEditingEvent(raw)
        if (!evt || !evt.node_id) {
          continue
        }
        if (evt.editing && evt.user_id && evt.color && evt.emoji) {
          const editor: ActiveEditor = {
            user_id: evt.user_id,
            username: resolveWorkshopEditorDisplayName(deps, evt.user_id, evt.username),
            color: evt.color,
            emoji: evt.emoji,
          }
          deps.activeEditors.value.set(evt.node_id, editor)
          if (deps.onNodeEditing) {
            deps.onNodeEditing(evt.node_id, editor)
          }
        } else {
          deps.activeEditors.value.delete(evt.node_id)
          if (deps.onNodeEditing) {
            deps.onNodeEditing(evt.node_id, null)
          }
        }
      }
      break
    }

    case 'room_idle_warning':
      deps.applyRoomIdleWarningFromServer(message)
      break

    case 'session_closing':
      deps.notify.info(deps.t('workshopCanvas.sessionEndedByHost'))
      break

    case 'owner_disconnected':
      if (message.workshop_continues) {
        deps.notify.info(deps.t('workshopCanvas.connectionClosed'))
      }
      break

    case 'kicked':
      if (message.reason === 'room_idle') {
        deps.clearRoomIdleCountdownUi()
      } else if (message.reason === 'session_ended') {
        deps.notify.info(deps.t('workshopCanvas.sessionEndedByHost'))
      } else if (message.reason === 'replaced_by_new_session') {
        deps.notify.warning(deps.t('workshopCanvas.connectionClosed'))
      } else if (message.reason) {
        deps.notify.warning(
          deps.t('workshopCanvas.connectionClosedReason', { reason: message.reason })
        )
      } else {
        deps.notify.warning(deps.t('workshopCanvas.connectionClosed'))
      }
      if (
        message.reason != null &&
        GUEST_FORCED_EXIT_KICK_REASONS.has(message.reason) &&
        workshopGuestEligibleForForcedExit(deps)
      ) {
        deps.onGuestForcedExit?.({ reason: message.reason })
      }
      break

    case 'error':
      if (import.meta.env.DEV) {
        console.warn('[CollabDebug] backend error received', {
          code: message.code,
          message: message.message,
        })
      }
      // Partial filter: some nodes were dropped by lock filters but the update
      // partially succeeded. Show a warning (not an error) and do not resync.
      if (message.code === 'update_partial_filtered') {
        const rawIds = message.filtered_node_ids
        const ids = Array.isArray(rawIds)
          ? rawIds.filter((x): x is string => typeof x === 'string' && x.length > 0)
          : []
        if (ids.length > 0) {
          eventBus.emit('workshop:partial-filtered', { nodeIds: ids })
        }
        deps.notify.warning(
          ids.length > 0
            ? deps.t('workshopCanvas.updatePartialFiltered', { count: ids.length })
            : message.message || deps.t('workshopCanvas.errorGeneric')
        )
        break
      }
      deps.notify.error(message.message || deps.t('workshopCanvas.errorGeneric'))
      if (
        message.code === 'update_rejected' ||
        (typeof message.message === 'string' &&
          message.message.toLowerCase().includes('update rejected'))
      ) {
        const resyncDiagramId = deps.mutable.sessionDiagramId ?? deps.diagramId.value
        if (resyncDiagramId && socket.readyState === WebSocket.OPEN) {
          deps.version.recordError('update_rejected')
          deps.schedulePendingResyncWatchdog(socket)
          socket.send(
            JSON.stringify({
              type: 'resync',
              diagram_id: resyncDiagramId,
            })
          )
        }
      }
      break

    case 'update_ack': {
      // Server confirmed the sender's update was merged and assigned it a seq
      // and version. Advance the ordering cursors so subsequent broadcasts from
      // peers are not treated as a gap and dropped.
      const rawAckId =
        typeof message.client_op_id === 'string' && message.client_op_id
          ? message.client_op_id
          : null
      const ackedNodeIds = deps.collectAcknowledgedNodeIds(rawAckId)
      const ackResult = deps.version.recordAck(message.version, message.seq)
      deps.acknowledgeOutboundUpdate(rawAckId)
      if (ackResult.peerGap && !deps.version.pendingResync.value) {
        const resyncDiagramId = deps.mutable.sessionDiagramId ?? deps.diagramId.value
        if (resyncDiagramId && socket.readyState === WebSocket.OPEN) {
          if (import.meta.env.DEV) {
            console.warn('[CollabSync] update_ack peer-gap — requesting resync', {
              version: message.version,
              seq: message.seq,
            })
          }
          deps.version.setPendingResync(true)
          deps.schedulePendingResyncWatchdog(socket)
          socket.send(JSON.stringify({ type: 'resync', diagram_id: resyncDiagramId }))
        }
      }
      if (import.meta.env.DEV) {
        console.log('[CollabSync] update_ack received', {
          version: message.version,
          seq: message.seq,
          liveSeq: deps.version.liveSeq.value,
          liveVersion: deps.version.liveVersion.value,
          peerGap: ackResult.peerGap,
        })
      }
      eventBus.emit('workshop:collab-ack', { nodeIds: ackedNodeIds })
      break
    }

    case 'pong':
      deps.recordTransportPong()
      break

    case 'role_changed':
      if (message.role) {
        deps.workshopRole.value = message.role
        eventBus.emit('workshop:role-changed', {
          userId: message.user_id,
          role: message.role,
        })
      }
      break

    case 'role_change_ack':
      break

    case 'write_locked': {
      const writingUserId = message.user_id
      if (writingUserId == null) {
        break
      }
      eventBus.emit('workshop:write-locked', {
        userId: writingUserId,
        locked: message.locked === true,
      })
      break
    }

    case 'node_edit_claimed': {
      const claimedNodeId = message.node_id
      if (!claimedNodeId) break
      if (message.granted === true) {
        // Server confirmed the claim — already in edit mode, nothing to do.
        break
      }
      // Server denied the claim: another user holds the lock.
      // Update activeEditors immediately so collabForeignLockedNodeIds reflects
      // the holder before the broadcast node_editing frame arrives, preventing
      // a race window where a second click could attempt another edit.
      let deniedHolderLabel = message.held_by_username ?? ''
      if (message.held_by_user_id != null) {
        deniedHolderLabel = resolveWorkshopEditorDisplayName(
          deps,
          message.held_by_user_id,
          message.held_by_username
        )
        const existing = deps.activeEditors.value.get(claimedNodeId)
        if (!existing || existing.user_id !== message.held_by_user_id) {
          const updated = new Map(deps.activeEditors.value)
          updated.set(claimedNodeId, {
            user_id: message.held_by_user_id,
            username: deniedHolderLabel,
            color: existing?.color ?? '',
            emoji: existing?.emoji ?? '',
          })
          deps.activeEditors.value = updated
        }
      }
      eventBus.emit('workshop:node-edit-denied', {
        nodeId: claimedNodeId,
        heldByUsername: deniedHolderLabel,
      })
      break
    }

    default:
      break
  }
}
