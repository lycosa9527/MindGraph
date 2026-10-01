/**
 * Active embedded MindMate collab room on /mindmate (sidebar highlight + navigation).
 *
 * The seminar WebSocket stays up after this view closes. This code is only
 * how MindMate finds the room again after a full reload.
 */
import { ref } from 'vue'

import {
  formatMindmateCollabCode,
  normalizeMindmateCollabCode,
  wasMindmateCollabCodeRecentlyEnded,
} from '@/utils/mindmateCollabSessions'

export const MINDMATE_COLLAB_ACTIVE_ROOM_KEY = 'mindmate_collab_active_room'
export const MINDMATE_COLLAB_JOINED_ROOMS_KEY = 'mindmate_collab_joined_rooms'

export const embeddedCollabRoomCode = ref<string | null>(null)

function writeActiveRoom(code: string | null): void {
  if (typeof sessionStorage === 'undefined') {
    return
  }
  try {
    if (code) {
      sessionStorage.setItem(MINDMATE_COLLAB_ACTIVE_ROOM_KEY, code)
    } else {
      sessionStorage.removeItem(MINDMATE_COLLAB_ACTIVE_ROOM_KEY)
    }
  } catch {
    // privacy mode / quota
  }
}

export function setEmbeddedCollabRoomCode(code: string | null): void {
  if (code && wasMindmateCollabCodeRecentlyEnded(code)) {
    return
  }
  const next = code ? formatMindmateCollabCode(code) : null
  embeddedCollabRoomCode.value = next
  writeActiveRoom(next)
}

/** Restore the seminar after a full reload. In-tab navigation keeps the ref. */
export function hydrateEmbeddedCollabRoomCode(): void {
  if (embeddedCollabRoomCode.value) {
    return
  }
  if (typeof sessionStorage === 'undefined') {
    return
  }
  let stored: string | null
  try {
    stored = sessionStorage.getItem(MINDMATE_COLLAB_ACTIVE_ROOM_KEY)
  } catch {
    return
  }
  if (!stored) {
    return
  }
  if (wasMindmateCollabCodeRecentlyEnded(stored)) {
    writeActiveRoom(null)
    return
  }
  embeddedCollabRoomCode.value = formatMindmateCollabCode(stored)
}

function readJoinedRooms(): string[] {
  if (typeof sessionStorage === 'undefined') {
    return []
  }
  try {
    const raw = sessionStorage.getItem(MINDMATE_COLLAB_JOINED_ROOMS_KEY)
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed.filter(
      (item): item is string => typeof item === 'string' && item.trim().length > 0
    )
  } catch {
    return []
  }
}

function writeJoinedRooms(codes: string[]): void {
  if (typeof sessionStorage === 'undefined') {
    return
  }
  try {
    if (codes.length === 0) {
      sessionStorage.removeItem(MINDMATE_COLLAB_JOINED_ROOMS_KEY)
      return
    }
    sessionStorage.setItem(MINDMATE_COLLAB_JOINED_ROOMS_KEY, JSON.stringify(codes))
  } catch {
    // privacy mode / quota
  }
}

/** Seminars whose sockets should reopen after a reload. */
export function loadJoinedCollabRooms(): string[] {
  return readJoinedRooms()
}

export function rememberJoinedCollabRoom(code: string): void {
  if (!code.trim() || wasMindmateCollabCodeRecentlyEnded(code)) {
    return
  }
  const formatted = formatMindmateCollabCode(code)
  const key = normalizeMindmateCollabCode(formatted)
  const next = readJoinedRooms().filter((item) => normalizeMindmateCollabCode(item) !== key)
  next.push(formatted)
  writeJoinedRooms(next)
}

export function forgetJoinedCollabRoom(code: string): void {
  if (!code.trim()) {
    return
  }
  const key = normalizeMindmateCollabCode(code)
  writeJoinedRooms(readJoinedRooms().filter((item) => normalizeMindmateCollabCode(item) !== key))
}
