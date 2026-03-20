/**
 * Persist workshop channel list and per-channel topic lists in localStorage
 * to avoid refetching on every navigation (TTL-based, user/org scoped).
 * Stores optional ETag for conditional GET revalidation after TTL.
 */

import type { ChatChannel, ChatTopic } from '@/stores/workshopChat'

const PREFIX = 'mg_ws_v1'
/** Default TTL for channel list (product-tunable). */
export const CHANNELS_TTL_MS = 20 * 60 * 1000
/** Default TTL for per-channel topic lists. */
export const TOPICS_TTL_MS = 12 * 60 * 1000

export interface WorkshopCacheScope {
  userId: string
  /** Admin org picker or school id string for API scope. */
  orgKey: string
}

export function buildWorkshopCacheScope(
  userId: string | undefined,
  adminOrgId: number | null,
  schoolId: string | undefined,
): WorkshopCacheScope | null {
  if (!userId) {
    return null
  }
  const orgKey = adminOrgId != null ? `a${adminOrgId}` : `s${schoolId ?? 'none'}`
  return { userId, orgKey }
}

export interface WorkshopChannelsCacheRow {
  savedAt: number
  data: ChatChannel[]
  etag: string | null
}

export interface WorkshopTopicsCacheRow {
  savedAt: number
  data: ChatTopic[]
  etag: string | null
}

function channelsKey(scope: WorkshopCacheScope): string {
  return `${PREFIX}_ch_${scope.userId}_${scope.orgKey}`
}

function topicsKey(scope: WorkshopCacheScope, channelId: number): string {
  return `${PREFIX}_tp_${scope.userId}_${scope.orgKey}_${channelId}`
}

function parseChannelsRow(raw: string): WorkshopChannelsCacheRow | null {
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>
    if (
      typeof parsed !== 'object'
      || parsed === null
      || typeof parsed.savedAt !== 'number'
      || !Array.isArray(parsed.data)
    ) {
      return null
    }
    const etag = typeof parsed.etag === 'string' ? parsed.etag : null
    return {
      savedAt: parsed.savedAt,
      data: parsed.data as ChatChannel[],
      etag,
    }
  } catch {
    return null
  }
}

function parseTopicsRow(raw: string): WorkshopTopicsCacheRow | null {
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>
    if (
      typeof parsed !== 'object'
      || parsed === null
      || typeof parsed.savedAt !== 'number'
      || !Array.isArray(parsed.data)
    ) {
      return null
    }
    const etag = typeof parsed.etag === 'string' ? parsed.etag : null
    return {
      savedAt: parsed.savedAt,
      data: (parsed.data as ChatTopic[]).map(t => ({
        ...t,
        unread_count: t.unread_count ?? 0,
      })),
      etag,
    }
  } catch {
    return null
  }
}

export function readCachedChannelsRow(
  scope: WorkshopCacheScope,
): WorkshopChannelsCacheRow | null {
  try {
    const raw = localStorage.getItem(channelsKey(scope))
    if (!raw) {
      return null
    }
    return parseChannelsRow(raw)
  } catch {
    return null
  }
}

export function writeCachedChannels(
  scope: WorkshopCacheScope,
  channels: ChatChannel[],
  etag: string | null,
): void {
  try {
    const payload = {
      savedAt: Date.now(),
      data: channels,
      etag,
    }
    localStorage.setItem(channelsKey(scope), JSON.stringify(payload))
  } catch {
    /* quota / private mode */
  }
}

export function touchCachedChannels(scope: WorkshopCacheScope): void {
  const row = readCachedChannelsRow(scope)
  if (!row) {
    return
  }
  writeCachedChannels(scope, row.data, row.etag)
}

export function readCachedTopicsRow(
  scope: WorkshopCacheScope,
  channelId: number,
): WorkshopTopicsCacheRow | null {
  try {
    const raw = localStorage.getItem(topicsKey(scope, channelId))
    if (!raw) {
      return null
    }
    return parseTopicsRow(raw)
  } catch {
    return null
  }
}

export function writeCachedTopics(
  scope: WorkshopCacheScope,
  channelId: number,
  topics: ChatTopic[],
  etag: string | null,
): void {
  try {
    const payload = {
      savedAt: Date.now(),
      data: topics.map(t => ({
        ...t,
        unread_count: t.unread_count ?? 0,
      })),
      etag,
    }
    localStorage.setItem(topicsKey(scope, channelId), JSON.stringify(payload))
  } catch {
    /* quota / private mode */
  }
}

export function touchCachedTopics(
  scope: WorkshopCacheScope,
  channelId: number,
): void {
  const row = readCachedTopicsRow(scope, channelId)
  if (!row) {
    return
  }
  writeCachedTopics(scope, channelId, row.data, row.etag)
}

export function clearCachedTopics(
  scope: WorkshopCacheScope,
  channelId: number,
): void {
  try {
    localStorage.removeItem(topicsKey(scope, channelId))
  } catch {
    /* ignore */
  }
}

/** Remove all workshop cache entries for this user (logout / reset). */
export function clearWorkshopChatCachesForUser(userId: string): void {
  try {
    const chPrefix = `${PREFIX}_ch_${userId}_`
    const tpPrefix = `${PREFIX}_tp_${userId}_`
    const toRemove: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (k && (k.startsWith(chPrefix) || k.startsWith(tpPrefix))) {
        toRemove.push(k)
      }
    }
    for (const k of toRemove) {
      localStorage.removeItem(k)
    }
  } catch {
    /* ignore */
  }
}

export function cacheIsFresh(savedAt: number, ttlMs: number): boolean {
  return Date.now() - savedAt <= ttlMs
}
