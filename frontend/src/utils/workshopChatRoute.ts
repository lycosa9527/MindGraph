/**
 * Workshop Chat URL state (Zulip-style narrows): channel, topic, DM, browse, optional message focus.
 */
import type { LocationQuery } from 'vue-router'

export const WORKSHOP_CHAT_PATH = '/workshop-chat'

export type WorkshopRouteQueryState = {
  currentChannelId: number | null
  currentTopicId: number | null
  currentDMPartnerId: number | null
  showChannelBrowser: boolean
  workshopHomeViewActive: boolean
  /** Main channel stream (topic_id null) when a channel is selected without a topic. */
  mainChannelFeedActive: boolean
  /** Teaching group (教研组) overview in the center column — no lesson channel selected. */
  teachingGroupLandingId?: number | null
  /** When set, adds `message=` for deep links to a specific post (topic, stream, or DM). */
  focusMessageId?: number | null
}

export type WorkshopParsedRoute =
  | { kind: 'home' }
  | { kind: 'browse' }
  | { kind: 'dm'; partnerId: number }
  | { kind: 'teachingGroup'; groupId: number }
  | { kind: 'channel'; channelId: number; topicId: number | null; mainStream: boolean }

const Q = {
  channel: 'channel',
  topic: 'topic',
  dm: 'dm',
  browse: 'browse',
  stream: 'stream',
  message: 'message',
  group: 'group',
} as const

/** Keys that define narrow identity (excludes `message`, which is a one-shot focus). */
const NARROW_KEYS: readonly string[] = [Q.channel, Q.topic, Q.dm, Q.browse, Q.stream, Q.group]

function firstQueryValue(query: LocationQuery, key: string): string {
  const v = query[key]
  if (v == null) return ''
  if (Array.isArray(v)) {
    const x = v[0]
    return x == null ? '' : String(x)
  }
  return String(v)
}

function withOptionalMessage(
  payload: Record<string, string>,
  focusMessageId?: number | null
): Record<string, string> {
  if (focusMessageId != null && focusMessageId > 0) {
    return { ...payload, [Q.message]: String(focusMessageId) }
  }
  return payload
}

export function parseWorkshopChatRouteQuery(query: LocationQuery): WorkshopParsedRoute {
  const dmStr = firstQueryValue(query, Q.dm)
  if (dmStr !== '') {
    const partnerId = parseInt(dmStr, 10)
    if (Number.isFinite(partnerId)) {
      return { kind: 'dm', partnerId }
    }
  }
  const browse = firstQueryValue(query, Q.browse)
  if (browse === '1' || browse === 'true') {
    return { kind: 'browse' }
  }
  const groupStr = firstQueryValue(query, Q.group)
  if (groupStr !== '') {
    const groupId = parseInt(groupStr, 10)
    if (Number.isFinite(groupId)) {
      return { kind: 'teachingGroup', groupId }
    }
  }
  const chStr = firstQueryValue(query, Q.channel)
  if (chStr !== '') {
    const channelId = parseInt(chStr, 10)
    if (Number.isFinite(channelId)) {
      const topicStr = firstQueryValue(query, Q.topic)
      let topicId: number | null = null
      if (topicStr !== '') {
        const t = parseInt(topicStr, 10)
        if (Number.isFinite(t)) topicId = t
      }
      const streamStr = firstQueryValue(query, Q.stream)
      const mainStream = topicId == null && (streamStr === '1' || streamStr === 'true')
      return { kind: 'channel', channelId, topicId, mainStream }
    }
  }
  return { kind: 'home' }
}

/** `?message=` or `#msg-{id}` (hash may include leading `#`). */
export function parseWorkshopMessageFocus(route: {
  query: LocationQuery
  hash: string
}): number | null {
  const msgStr = firstQueryValue(route.query, Q.message)
  if (msgStr !== '') {
    const mid = parseInt(msgStr, 10)
    if (Number.isFinite(mid)) {
      return mid
    }
  }
  const h = (route.hash || '').trim()
  const m = /^#?msg-(\d+)$/.exec(h)
  if (m) {
    const mid = parseInt(m[1], 10)
    if (Number.isFinite(mid)) {
      return mid
    }
  }
  return null
}

export function workshopQueryFromState(state: WorkshopRouteQueryState): Record<string, string> {
  const fm = state.focusMessageId
  if (state.currentDMPartnerId != null) {
    return withOptionalMessage({ [Q.dm]: String(state.currentDMPartnerId) }, fm)
  }
  if (state.showChannelBrowser) {
    return withOptionalMessage({ [Q.browse]: '1' }, fm)
  }
  if (state.teachingGroupLandingId != null) {
    return withOptionalMessage({ [Q.group]: String(state.teachingGroupLandingId) }, fm)
  }
  if (state.workshopHomeViewActive) {
    return withOptionalMessage({}, fm)
  }
  if (state.currentChannelId != null && state.currentTopicId != null) {
    return withOptionalMessage(
      {
        [Q.channel]: String(state.currentChannelId),
        [Q.topic]: String(state.currentTopicId),
      },
      fm
    )
  }
  if (state.currentChannelId != null && state.mainChannelFeedActive) {
    return withOptionalMessage(
      {
        [Q.channel]: String(state.currentChannelId),
        [Q.stream]: '1',
      },
      fm
    )
  }
  if (state.currentChannelId != null) {
    return withOptionalMessage({ [Q.channel]: String(state.currentChannelId) }, fm)
  }
  return withOptionalMessage({}, fm)
}

/** Full query snapshot (includes `message`). */
export function normalizeWorkshopRouteQuery(query: LocationQuery): Record<string, string> {
  const out: Record<string, string> = {}
  for (const key of Object.values(Q)) {
    const s = firstQueryValue(query, key)
    if (s !== '') out[key] = s
  }
  return out
}

/** Narrow identity only — use when comparing URL to Pinia-derived workshop state. */
export function normalizeWorkshopNarrowQuery(query: LocationQuery): Record<string, string> {
  const out: Record<string, string> = {}
  for (const key of NARROW_KEYS) {
    const s = firstQueryValue(query, key)
    if (s !== '') out[key] = s
  }
  return out
}

export function workshopRouteQueriesEqual(
  a: Record<string, string>,
  b: Record<string, string>
): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)])
  for (const k of keys) {
    if ((a[k] ?? '') !== (b[k] ?? '')) return false
  }
  return true
}

/** Relative path for sharing (e.g. copy link). */
export function workshopChatHrefFromState(state: WorkshopRouteQueryState): string {
  const q = workshopQueryFromState(state)
  const params = new URLSearchParams(q)
  const qs = params.toString()
  return qs ? `${WORKSHOP_CHAT_PATH}?${qs}` : WORKSHOP_CHAT_PATH
}
