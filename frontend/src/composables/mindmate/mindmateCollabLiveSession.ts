/**
 * MindMate seminar sockets for the whole tab.
 *
 * Each joined room keeps its own WebSocket. Leaving the chat view does not
 * close it. A socket closes when that room's owner ends the seminar, the room
 * shuts down, this user drops the room, or they sign out.
 */
import { type EffectScope, effectScope, onUnmounted, watch } from 'vue'

import {
  embeddedCollabRoomCode,
  forgetJoinedCollabRoom,
  loadJoinedCollabRooms,
  rememberJoinedCollabRoom,
  setEmbeddedCollabRoomCode,
} from '@/composables/mindmate/mindmateCollabEmbeddedBridge'
import {
  type MindmateCollabMessage,
  useMindmateCollab,
} from '@/composables/mindmate/useMindmateCollab'
import { clearSeminarFaces } from '@/composables/mindmate/useMindmateSeminarFaces'
import { useAuthStore } from '@/stores/auth'
import {
  normalizeMindmateCollabCode,
  wasMindmateCollabCodeRecentlyEnded,
} from '@/utils/mindmateCollabSessions'
import {
  removeLocalMindmateCollabSessionByCode,
  shouldRemoveCollabFromHistory,
} from '@/utils/mindmateCollabTeardown'
import type { MindmateCollabConnectionStatus } from '@/utils/mindmateCollabWsErrors'

type SessionEndedReason = 'idle' | 'host'
type CollabSession = ReturnType<typeof useMindmateCollab>

interface LiveRoom {
  code: string
  session: CollabSession
  seedMessages: () => MindmateCollabMessage[]
  endedListeners: Set<(reason: SessionEndedReason) => void>
}

let scope: EffectScope | null = null
let authWatchStarted = false
const rooms = new Map<string, LiveRoom>()
let visibleKey: string | null = null

function roomKey(code: string): string {
  return normalizeMindmateCollabCode(code)
}

function ensureScope(): EffectScope {
  if (!scope) {
    scope = effectScope(true)
  }
  return scope
}

function embeddedMatches(code: string): boolean {
  const current = embeddedCollabRoomCode.value
  if (!current) {
    return false
  }
  return roomKey(current) === roomKey(code)
}

function finishRoom(key: string, reason: SessionEndedReason): void {
  const entry = rooms.get(key)
  if (!entry) {
    return
  }
  rooms.delete(key)
  forgetJoinedCollabRoom(entry.code)
  if (shouldRemoveCollabFromHistory(reason)) {
    removeLocalMindmateCollabSessionByCode(entry.code)
  }
  const showing = visibleKey === key
  if (showing) {
    visibleKey = null
    clearSeminarFaces()
    for (const handler of [...entry.endedListeners]) {
      handler(reason)
    }
  }
  if (embeddedMatches(entry.code)) {
    setEmbeddedCollabRoomCode(null)
  }
}

function closeAllLiveCollabRooms(): void {
  const open = [...rooms.values()]
  rooms.clear()
  visibleKey = null
  for (const entry of open) {
    entry.session.disconnect()
    forgetJoinedCollabRoom(entry.code)
  }
  for (const stored of loadJoinedCollabRooms()) {
    forgetJoinedCollabRoom(stored)
  }
  setEmbeddedCollabRoomCode(null)
  clearSeminarFaces()
}

function armAuthWatch(): void {
  if (authWatchStarted) {
    return
  }
  authWatchStarted = true
  ensureScope().run(() => {
    const authStore = useAuthStore()
    watch(
      () => [authStore.isAuthenticated, authStore.isAuthSessionVerified] as const,
      ([signedIn, verified]) => {
        if (!signedIn) {
          closeAllLiveCollabRooms()
          return
        }
        if (verified) {
          restoreJoinedMindmateCollabSockets()
        }
      }
    )
  })
}

function ensureRoom(code: string): LiveRoom {
  armAuthWatch()
  const key = roomKey(code)
  const existing = rooms.get(key)
  if (existing) {
    return existing
  }
  const entry: LiveRoom = {
    code,
    session: null as unknown as CollabSession,
    seedMessages: () => [],
    endedListeners: new Set(),
  }
  const created = ensureScope().run(() =>
    useMindmateCollab(() => rooms.get(key)?.code ?? code, {
      embedded: true,
      seedMessages: () => entry.seedMessages(),
      isForeground: () => visibleKey === key,
      onSessionEnded: (reason) => finishRoom(key, reason),
    })
  )
  if (!created) {
    throw new Error('MindMate collab session did not start')
  }
  entry.session = created
  rooms.set(key, entry)
  return entry
}

function connectRoom(entry: LiveRoom): void {
  if (!collabSocketCoversCode(entry.code, entry.session.connectionStatus.value, entry.code)) {
    entry.session.connect()
  }
  rememberJoinedCollabRoom(entry.code)
}

export function collabSocketCoversCode(
  openCode: string | null,
  status: MindmateCollabConnectionStatus,
  requestedCode: string
): boolean {
  if (!openCode || !requestedCode) {
    return false
  }
  if (roomKey(openCode) !== roomKey(requestedCode)) {
    return false
  }
  return status === 'connected' || status === 'connecting' || status === 'reconnecting'
}

export function mindmateCollabLiveCovers(code: string): boolean {
  const entry = rooms.get(roomKey(code))
  if (!entry) {
    return false
  }
  return collabSocketCoversCode(entry.code, entry.session.connectionStatus.value, code)
}

/** Close one seminar without touching the others. */
export function dropLiveCollabRoom(code: string): void {
  if (!code.trim()) {
    return
  }
  const key = roomKey(code)
  const entry = rooms.get(key)
  forgetJoinedCollabRoom(code)
  if (!entry) {
    return
  }
  rooms.delete(key)
  entry.session.disconnect()
  if (visibleKey === key) {
    visibleKey = null
    clearSeminarFaces()
  }
}

/** Reopen every seminar this tab joined, after auth is ready. */
export function restoreJoinedMindmateCollabSockets(): void {
  const authStore = useAuthStore()
  if (!authStore.isAuthenticated || !authStore.isAuthSessionVerified) {
    return
  }
  for (const code of loadJoinedCollabRooms()) {
    if (wasMindmateCollabCodeRecentlyEnded(code)) {
      forgetJoinedCollabRoom(code)
      continue
    }
    connectRoom(ensureRoom(code))
  }
}

export function installMindmateCollabLiveSession(): void {
  armAuthWatch()
  restoreJoinedMindmateCollabSockets()
}

export function useLiveMindmateCollab(
  code: string,
  view: {
    onSessionEnded?: (reason: SessionEndedReason) => void
    seedMessages?: () => MindmateCollabMessage[]
  }
) {
  const entry = ensureRoom(code)
  const key = roomKey(code)
  visibleKey = key
  if (view.seedMessages) {
    entry.seedMessages = view.seedMessages
  }
  entry.session.publishSeminarFaces()
  const onEnded = view.onSessionEnded
  if (onEnded) {
    entry.endedListeners.add(onEnded)
    onUnmounted(() => {
      entry.endedListeners.delete(onEnded)
    })
  }
  onUnmounted(() => {
    if (visibleKey === key) {
      visibleKey = null
    }
  })
  return entry.session
}
