/**
 * Workshop Chat Pinia Store
 *
 * Central state management for channels, topics, DMs, unread counts, and presence.
 * Works with useWorkshopChat composable for WebSocket integration.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import { apiRequest } from '@/utils/apiClient'
import {
  CHANNELS_TTL_MS,
  TOPICS_TTL_MS,
  type WorkshopCacheScope,
  buildWorkshopCacheScope,
  cacheIsFresh,
  clearCachedTopics,
  clearWorkshopChatCachesForUser,
  readCachedChannelsRow,
  readCachedTopicsRow,
  touchCachedChannels,
  touchCachedTopics,
  writeCachedChannels,
  writeCachedTopics,
} from '@/utils/workshopChatLocalCache'
import {
  loadLastSeenOnlineFromStorage,
  saveLastSeenOnlineToStorage,
} from '@/utils/workshopContactLastSeenStorage'
import { registerWorkshopChatResetOnAuthClear } from '@/utils/workshopChatWsRegistry'

export interface ChatChannel {
  id: number
  name: string
  description: string | null
  avatar: string | null
  created_by: number
  channel_type: 'announce' | 'public' | 'private'
  is_default: boolean
  posting_policy: string
  can_post: boolean
  member_count: number
  topic_count: number
  is_joined: boolean
  is_muted: boolean
  pin_to_top: boolean
  color: string
  desktop_notifications?: boolean
  email_notifications?: boolean
  unread_count: number
  created_at: string
  parent_id: number | null
  /** Top-level teaching groups: persisted sidebar order (lower first). */
  display_order?: number
  status?: string | null
  deadline?: string | null
  diagram_id?: string | null
  is_resolved?: boolean
  children?: ChatChannel[]
}

export interface ChatTopic {
  id: number
  channel_id: number
  title: string
  description: string | null
  created_by: number
  creator_name: string | null
  visibility_policy: 'inherit' | 'muted' | 'unmuted' | 'followed'
  message_count: number
  /** Messages newer than the user's last read cursor for this topic. */
  unread_count: number
  created_at: string
  updated_at: string
}

let channelsInflight: { key: string; promise: Promise<void> } | null = null

function workshopScopeKey(scope: WorkshopCacheScope | null): string {
  if (!scope) {
    return '_'
  }
  return `${scope.userId}:${scope.orgKey}`
}

type TopicsFetchOutcome =
  | { kind: 'http304' }
  | { kind: 'http200'; raw: ChatTopic[]; etag: string | null }
  | { kind: 'error' }

const topicsInflight = new Map<string, Promise<TopicsFetchOutcome>>()

function clearWorkshopListInflight(): void {
  channelsInflight = null
  topicsInflight.clear()
}

export interface ChatMessage {
  id: number
  channel_id: number
  topic_id: number | null
  sender_id: number
  sender_name: string
  sender_avatar: string | null
  content: string
  message_type: string
  parent_id: number | null
  is_deleted?: boolean
  /** Server-resolved user IDs for @**Name** mentions (same org + admins + staff list). */
  mentioned_user_ids?: number[]
  created_at: string
  edited_at: string | null
}

export interface DirectMessageItem {
  id: number
  sender_id: number
  recipient_id: number
  content: string
  message_type: string
  is_read: boolean
  mentioned_user_ids?: number[]
  created_at: string
  edited_at: string | null
}

export interface DMConversation {
  partner_id: number
  partner_name: string
  partner_avatar: string | null
  last_message: {
    content: string | null
    created_at: string | null
    is_mine: boolean
  }
  unread_count: number
}

export interface ChannelMember {
  user_id: number
  name: string
  avatar: string | null
  role: string
  joined_at: string
}

export interface OrgMember {
  id: number
  name: string
  avatar: string | null
  /** ISO 8601 from server: last workshop chat org-presence disconnect. */
  last_seen_at?: string | null
}

export interface OrgMembersPage {
  items: OrgMember[]
  total: number
  limit: number
  offset: number
}

const DEFAULT_ORG_MEMBER_PAGE_SIZE = 200

export interface AdminOrg {
  id: number
  code: string
  name: string
  user_count: number
}

export interface ReactionGroup {
  emoji_name: string
  emoji_code: string
  count: number
  user_ids: number[]
  reacted: boolean
}

export interface FileAttachment {
  id: number
  message_id: number | null
  dm_id: number | null
  uploader_id: number
  filename: string
  content_type: string
  file_size: number
  file_path: string
  created_at: string
}

export const useWorkshopChatStore = defineStore('workshopChat', () => {
  const channels = ref<ChatChannel[]>([])
  const currentChannelId = ref<number | null>(null)
  const currentTopicId = ref<number | null>(null)
  const currentDMPartnerId = ref<number | null>(null)

  const topics = ref<ChatTopic[]>([])
  const channelMessages = ref<ChatMessage[]>([])
  const topicMessages = ref<ChatMessage[]>([])
  const dmConversations = ref<DMConversation[]>([])
  const dmMessages = ref<DirectMessageItem[]>([])
  const channelMembers = ref<ChannelMember[]>([])

  const activeTab = ref<'channels' | 'dms'>('channels')

  const onlineUserIds = ref<Set<number>>(new Set())
  /** Last time user was seen online (ms); used for "recently online" when they disconnect. */
  const lastSeenOnlineAtByUserId = ref<Record<number, number>>({})
  const typingUsers = ref<
    Map<string, { username: string; timeout: ReturnType<typeof setTimeout> }>
  >(new Map())

  const loading = ref(false)

  const orgMembers = ref<OrgMember[]>([])
  /** Total matching the last org-members query (search or full roster). */
  const orgMembersTotal = ref(0)
  /** `q` for the current loaded slice (for load-more). */
  const orgMembersListQuery = ref('')
  const adminOrgs = ref<AdminOrg[]>([])
  const adminOrgId = ref<number | null>(null)

  const messageReactions = ref<Map<number, ReactionGroup[]>>(new Map())
  const starredMessageIds = ref<Set<number>>(new Set())
  const messageAttachments = ref<Map<number, FileAttachment[]>>(new Map())

  const showChannelBrowser = ref(false)
  /** When true, main pane shows inbox / welcome instead of a channel or DM. */
  const workshopHomeViewActive = ref(false)
  /** True: center column shows topic_id-null stream instead of the topic grid. */
  const mainChannelFeedActive = ref(false)
  const dialogChannelSettingsId = ref<number | null>(null)
  const dialogTopicEdit = ref<{
    topicId: number
    channelId: number
    mode: 'rename' | 'move'
  } | null>(null)

  /** Create-channel dialog (gear menu or “add lesson study” on a 教研组). */
  const createChannelDialogVisible = ref(false)
  const createChannelPrefillParentId = ref<number | null>(null)
  /** WorkshopChatPage opens new-topic dialog when set. */
  const newTopicDialogRequestChannelId = ref<number | null>(null)
  /**
   * Teaching group (教研组) selected: middle column shows overview (Zulip stream
   * narrow) without selecting a lesson-study channel.
   */
  const teachingGroupLandingId = ref<number | null>(null)

  const currentChannel = computed(() => {
    if (currentChannelId.value === null) return null
    return findChannelById(currentChannelId.value)
  })

  const topicParticipantIds = computed<Set<number>>(() => {
    const ids = new Set<number>()
    const msgs = currentTopicId.value ? topicMessages.value : channelMessages.value
    for (const msg of msgs) {
      ids.add(msg.sender_id)
    }
    return ids
  })

  const joinedChannels = computed(() => channels.value.filter((c) => c.is_joined))

  const totalUnreadChannels = computed(() =>
    channels.value.reduce((sum, c) => sum + (c.is_joined ? c.unread_count : 0), 0)
  )

  const totalUnreadDMs = computed(() =>
    dmConversations.value.reduce((sum, c) => sum + c.unread_count, 0)
  )

  const announceChannels = computed(() =>
    channels.value.filter((c) => c.channel_type === 'announce')
  )

  const publicChannels = computed(() => channels.value.filter((c) => c.channel_type === 'public'))

  const privateChannels = computed(() => channels.value.filter((c) => c.channel_type === 'private'))

  const pinnedChannels = computed(() => channels.value.filter((c) => c.pin_to_top && c.is_joined))

  const channelGroups = computed(() =>
    channels.value.filter((c) => c.parent_id === null || c.parent_id === undefined)
  )

  const allLessonStudies = computed(() => channels.value.flatMap((g) => g.children ?? []))

  function findChannelById(channelId: number): ChatChannel | null {
    for (const group of channels.value) {
      if (group.id === channelId) return group
      for (const child of group.children ?? []) {
        if (child.id === channelId) return child
      }
    }
    return null
  }

  function findParentGroup(channelId: number): ChatChannel | null {
    for (const group of channels.value) {
      for (const child of group.children ?? []) {
        if (child.id === channelId) return group
      }
    }
    return null
  }

  function getCacheScope(): WorkshopCacheScope | null {
    const auth = useAuthStore()
    return buildWorkshopCacheScope(auth.user?.id, adminOrgId.value, auth.user?.schoolId)
  }

  function applyTopicsPayload(channelId: number, raw: ChatTopic[], merge: boolean): void {
    const mapped = raw.map((t) => ({
      ...t,
      unread_count: t.unread_count ?? 0,
    }))
    if (merge) {
      const rest = topics.value.filter((t) => t.channel_id !== channelId)
      topics.value = [...rest, ...mapped]
    } else {
      topics.value = mapped
    }
  }

  async function initializeDefaults(): Promise<void> {
    try {
      const res = await apiRequest('/api/chat/channels/initialize', { method: 'POST' })
      if (!res.ok) {
        console.warn('[WorkshopChat] initializeDefaults response:', res.status)
      }
    } catch (err) {
      console.warn('[WorkshopChat] initializeDefaults error:', err)
    }
  }

  async function fetchChannels(options?: { force?: boolean }): Promise<void> {
    const scope = getCacheScope()
    const skey = workshopScopeKey(scope)

    if (!options?.force && channelsInflight?.key === skey) {
      await channelsInflight.promise
      return
    }

    if (!options?.force && scope) {
      const row = readCachedChannelsRow(scope)
      if (row && cacheIsFresh(row.savedAt, CHANNELS_TTL_MS)) {
        channels.value = row.data
        return
      }
    }

    const run = async (): Promise<void> => {
      try {
        const orgParam = adminOrgId.value ? `?org_id=${adminOrgId.value}` : ''
        const headers: Record<string, string> = {}
        if (!options?.force && scope) {
          const row = readCachedChannelsRow(scope)
          if (row?.etag) {
            headers['If-None-Match'] = row.etag
          }
        }
        const res = await apiRequest(`/api/chat/channels${orgParam}`, { headers })
        if (res.status === 304 && scope) {
          touchCachedChannels(scope)
          return
        }
        if (res.ok && res.status === 200) {
          const data: ChatChannel[] = await res.json()
          channels.value = data
          if (scope) {
            writeCachedChannels(scope, data, res.headers.get('ETag'))
          }
        }
      } catch (err) {
        console.error('[WorkshopChat] fetchChannels error:', err)
      }
    }

    if (options?.force) {
      await run()
      return
    }

    const promise = run().finally(() => {
      if (channelsInflight?.key === skey) {
        channelsInflight = null
      }
    })
    channelsInflight = { key: skey, promise }
    await promise
  }

  async function fetchTopics(
    channelId: number,
    options?: { force?: boolean; merge?: boolean }
  ): Promise<void> {
    const scope = getCacheScope()
    const merge = options?.merge ?? false
    const skey = `${workshopScopeKey(scope)}:${channelId}`

    if (!options?.force && scope) {
      const row = readCachedTopicsRow(scope, channelId)
      if (row && cacheIsFresh(row.savedAt, TOPICS_TTL_MS)) {
        applyTopicsPayload(channelId, row.data, merge)
        return
      }
    }

    async function runTopicsNetwork(forceNet: boolean): Promise<TopicsFetchOutcome> {
      try {
        const headers: Record<string, string> = {}
        if (!forceNet && scope) {
          const row = readCachedTopicsRow(scope, channelId)
          if (row?.etag) {
            headers['If-None-Match'] = row.etag
          }
        }
        const res = await apiRequest(`/api/chat/channels/${channelId}/topics`, { headers })
        if (res.status === 304) {
          return { kind: 'http304' }
        }
        if (res.ok && res.status === 200) {
          const raw: ChatTopic[] = await res.json()
          const mapped = raw.map((t) => ({
            ...t,
            unread_count: t.unread_count ?? 0,
          }))
          const etag = res.headers.get('ETag')
          if (scope) {
            writeCachedTopics(scope, channelId, mapped, etag)
          }
          return { kind: 'http200', raw: mapped, etag }
        }
      } catch (err) {
        console.error('[WorkshopChat] fetchTopics error:', err)
      }
      return { kind: 'error' }
    }

    let outcome: TopicsFetchOutcome
    if (options?.force) {
      outcome = await runTopicsNetwork(true)
    } else {
      let shared = topicsInflight.get(skey)
      if (!shared) {
        shared = runTopicsNetwork(false).finally(() => {
          topicsInflight.delete(skey)
        })
        topicsInflight.set(skey, shared)
      }
      outcome = await shared
    }

    if (outcome.kind === 'http304') {
      if (scope) {
        touchCachedTopics(scope, channelId)
        const row = readCachedTopicsRow(scope, channelId)
        if (row) {
          applyTopicsPayload(channelId, row.data, merge)
        }
      }
      return
    }
    if (outcome.kind === 'http200') {
      applyTopicsPayload(channelId, outcome.raw, merge)
    }
  }

  async function fetchChannelMessages(
    channelId: number,
    anchor = 0,
    numBefore = 50,
    numAfter = 0
  ): Promise<ChatMessage[]> {
    try {
      const res = await apiRequest(
        `/api/chat/channels/${channelId}/messages` +
          `?anchor=${anchor}&num_before=${numBefore}&num_after=${numAfter}`
      )
      if (res.ok) {
        const msgs: ChatMessage[] = await res.json()
        const prependOlder = anchor > 0 && numAfter === 0
        if (prependOlder) {
          channelMessages.value = [...msgs, ...channelMessages.value]
        } else {
          channelMessages.value = msgs
        }
        return msgs
      }
    } catch (err) {
      console.error('[WorkshopChat] fetchChannelMessages error:', err)
    }
    return []
  }

  async function fetchTopicMessages(
    channelId: number,
    topicId: number,
    anchor = 0,
    numBefore = 50,
    numAfter = 0
  ): Promise<ChatMessage[]> {
    try {
      const res = await apiRequest(
        `/api/chat/channels/${channelId}/topics/${topicId}/messages` +
          `?anchor=${anchor}&num_before=${numBefore}&num_after=${numAfter}`
      )
      if (res.ok) {
        const msgs: ChatMessage[] = await res.json()
        const prependOlder = anchor > 0 && numAfter === 0
        if (prependOlder) {
          topicMessages.value = [...msgs, ...topicMessages.value]
        } else {
          topicMessages.value = msgs
        }
        return msgs
      }
    } catch (err) {
      console.error('[WorkshopChat] fetchTopicMessages error:', err)
    }
    return []
  }

  async function fetchDMConversations(): Promise<void> {
    try {
      const res = await apiRequest('/api/chat/dm/conversations')
      if (res.ok) {
        dmConversations.value = await res.json()
      }
    } catch (err) {
      console.error('[WorkshopChat] fetchDMConversations error:', err)
    }
  }

  async function fetchDMMessages(
    partnerId: number,
    anchor = 0,
    numBefore = 50,
    numAfter = 0
  ): Promise<DirectMessageItem[]> {
    try {
      const res = await apiRequest(
        `/api/chat/dm/${partnerId}/messages` +
          `?anchor=${anchor}&num_before=${numBefore}&num_after=${numAfter}`
      )
      if (res.ok) {
        const msgs: DirectMessageItem[] = await res.json()
        const prependOlder = anchor > 0 && numAfter === 0
        if (prependOlder) {
          dmMessages.value = [...msgs, ...dmMessages.value]
        } else {
          dmMessages.value = msgs
        }
        return msgs
      }
    } catch (err) {
      console.error('[WorkshopChat] fetchDMMessages error:', err)
    }
    return []
  }

  async function searchChannelMessages(
    channelId: number,
    query: string,
    limit = 40
  ): Promise<ChatMessage[]> {
    const raw = query.trim()
    if (raw.length < 2) {
      return []
    }
    try {
      const params = new URLSearchParams({ q: raw, limit: String(limit) })
      const res = await apiRequest(`/api/chat/channels/${channelId}/messages/search?${params}`)
      if (res.ok) {
        return (await res.json()) as ChatMessage[]
      }
    } catch (err) {
      console.error('[WorkshopChat] searchChannelMessages error:', err)
    }
    return []
  }

  async function searchTopicMessages(
    channelId: number,
    topicId: number,
    query: string,
    limit = 40
  ): Promise<ChatMessage[]> {
    const raw = query.trim()
    if (raw.length < 2) {
      return []
    }
    try {
      const params = new URLSearchParams({
        q: raw,
        topic_id: String(topicId),
        limit: String(limit),
      })
      const res = await apiRequest(`/api/chat/channels/${channelId}/messages/search?${params}`)
      if (res.ok) {
        return (await res.json()) as ChatMessage[]
      }
    } catch (err) {
      console.error('[WorkshopChat] searchTopicMessages error:', err)
    }
    return []
  }

  async function searchDMMessages(
    partnerId: number,
    query: string,
    limit = 40
  ): Promise<DirectMessageItem[]> {
    const raw = query.trim()
    if (raw.length < 2) {
      return []
    }
    try {
      const params = new URLSearchParams({ q: raw, limit: String(limit) })
      const res = await apiRequest(`/api/chat/dm/${partnerId}/messages/search?${params}`)
      if (res.ok) {
        return (await res.json()) as DirectMessageItem[]
      }
    } catch (err) {
      console.error('[WorkshopChat] searchDMMessages error:', err)
    }
    return []
  }

  async function fetchChannelMembers(channelId: number): Promise<void> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/members`)
      if (res.ok) {
        channelMembers.value = await res.json()
      }
    } catch (err) {
      console.error('[WorkshopChat] fetchChannelMembers error:', err)
    }
  }

  const orgMembersHasMore = computed(() => orgMembers.value.length < orgMembersTotal.value)

  function buildOrgMembersQueryString(params: Record<string, string>): string {
    const search = new URLSearchParams(params)
    if (adminOrgId.value != null) {
      search.set('org_id', String(adminOrgId.value))
    }
    const qs = search.toString()
    return qs ? `?${qs}` : ''
  }

  async function fetchOrgMembers(options?: {
    q?: string
    limit?: number
    offset?: number
    append?: boolean
  }): Promise<void> {
    try {
      const q = options?.q ?? ''
      const limit = options?.limit ?? DEFAULT_ORG_MEMBER_PAGE_SIZE
      const offset = options?.offset ?? 0
      const append = options?.append ?? false
      const params: Record<string, string> = {
        limit: String(limit),
        offset: String(offset),
      }
      if (q.trim()) {
        params.q = q.trim()
      }
      const res = await apiRequest(`/api/chat/org-members${buildOrgMembersQueryString(params)}`)
      if (!res.ok) {
        return
      }
      const data = (await res.json()) as OrgMembersPage
      orgMembersListQuery.value = q.trim()
      if (append) {
        orgMembers.value = [...orgMembers.value, ...data.items]
      } else {
        orgMembers.value = data.items
      }
      orgMembersTotal.value = data.total
    } catch (err) {
      console.error('[WorkshopChat] fetchOrgMembers error:', err)
    }
  }

  /** Server-side name filter for @mentions and channel “others” search (does not replace `orgMembers`). */
  async function searchOrgMembers(query: string, limit = 20): Promise<OrgMember[]> {
    const trimmed = query.trim()
    if (!trimmed) {
      return []
    }
    try {
      const params: Record<string, string> = {
        q: trimmed,
        limit: String(Math.min(Math.max(limit, 1), 200)),
        offset: '0',
      }
      const res = await apiRequest(`/api/chat/org-members${buildOrgMembersQueryString(params)}`)
      if (!res.ok) {
        return []
      }
      const data = (await res.json()) as OrgMembersPage
      return data.items
    } catch (err) {
      console.error('[WorkshopChat] searchOrgMembers error:', err)
      return []
    }
  }

  async function fetchAdminOrgs(): Promise<void> {
    try {
      const res = await apiRequest('/api/auth/admin/organizations')
      if (res.ok) {
        const data = await res.json()
        adminOrgs.value = data.map((org: Record<string, unknown>) => ({
          id: org.id as number,
          code: org.code as string,
          name: org.name as string,
          user_count: org.user_count as number,
        }))
      }
    } catch (err) {
      console.error('[WorkshopChat] fetchAdminOrgs error:', err)
    }
  }

  function hydrateLastSeenOnlineFromStorage(): void {
    const scope = getCacheScope()
    if (!scope) {
      lastSeenOnlineAtByUserId.value = {}
      return
    }
    lastSeenOnlineAtByUserId.value = loadLastSeenOnlineFromStorage(scope)
  }

  function persistLastSeenOnlineIfNeeded(): void {
    const scope = getCacheScope()
    if (!scope) {
      return
    }
    saveLastSeenOnlineToStorage(scope, lastSeenOnlineAtByUserId.value)
  }

  function setAdminOrgId(orgId: number | null): void {
    adminOrgId.value = orgId
    hydrateLastSeenOnlineFromStorage()
  }

  async function joinChannel(channelId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/join`, { method: 'POST' })
      if (res.ok) {
        await fetchChannels({ force: true })
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] joinChannel error:', err)
    }
    return false
  }

  async function leaveChannel(channelId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/leave`, { method: 'POST' })
      if (res.ok) {
        await fetchChannels({ force: true })
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] leaveChannel error:', err)
    }
    return false
  }

  async function archiveChannel(channelId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        await fetchChannels({ force: true })
        if (currentChannelId.value === channelId) {
          selectChannel(null)
        }
        if (teachingGroupLandingId.value === channelId) {
          openWorkshopInboxHome()
        }
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] archiveChannel error:', err)
    }
    return false
  }

  // ── Channel subscription helpers ──────────────────────────────

  async function toggleChannelMute(channelId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/mute`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        const ch = channels.value.find((c) => c.id === channelId)
        if (ch) ch.is_muted = data.is_muted
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] toggleChannelMute error:', err)
    }
    return false
  }

  async function toggleChannelPin(channelId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/pin`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        const ch = channels.value.find((c) => c.id === channelId)
        if (ch) ch.pin_to_top = data.pin_to_top
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] toggleChannelPin error:', err)
    }
    return false
  }

  async function markChannelReadAll(channelId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/read`, {
        method: 'POST',
      })
      if (res.ok) {
        const ch = channels.value.find((c) => c.id === channelId)
        if (ch) ch.unread_count = 0
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] markChannelReadAll error:', err)
    }
    return false
  }

  async function markDMPartnerRead(partnerId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/dm/${partnerId}/read`, {
        method: 'POST',
      })
      if (res.ok) {
        const conv = dmConversations.value.find((c) => c.partner_id === partnerId)
        if (conv) conv.unread_count = 0
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] markDMPartnerRead error:', err)
    }
    return false
  }

  async function updateChannelLessonStudy(
    channelId: number,
    body: { status?: string; deadline?: string | null; is_resolved?: boolean }
  ): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: body.status,
          deadline: body.deadline,
          is_resolved: body.is_resolved,
        }),
      })
      if (res.ok) {
        await fetchChannels({ force: true })
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] updateChannelLessonStudy error:', err)
    }
    return false
  }

  async function updateChannelPrefs(
    channelId: number,
    prefs: { color?: string; desktop_notifications?: boolean; email_notifications?: boolean }
  ): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/preferences`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(prefs),
      })
      if (res.ok) {
        const data = (await res.json()) as {
          color?: string
          desktop_notifications?: boolean
          email_notifications?: boolean
        }
        const ch = channels.value.find((c) => c.id === channelId)
        if (ch) {
          if (data.color != null) ch.color = data.color
          if (data.desktop_notifications != null) {
            ch.desktop_notifications = data.desktop_notifications
          }
          if (data.email_notifications != null) {
            ch.email_notifications = data.email_notifications
          }
        }
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] updateChannelPrefs error:', err)
    }
    return false
  }

  async function updateChannelPermissions(
    channelId: number,
    perms: { channel_type?: string; posting_policy?: string; is_default?: boolean }
  ): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/permissions`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(perms),
      })
      if (res.ok) {
        await fetchChannels({ force: true })
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] updateChannelPermissions error:', err)
    }
    return false
  }

  async function updateChannelDetails(
    channelId: number,
    body: {
      name?: string
      description?: string | null
      avatar?: string | null
    }
  ): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.ok) {
        await fetchChannels({ force: true })
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] updateChannelDetails error:', err)
    }
    return false
  }

  async function reorderTeachingGroups(orderedIds: number[]): Promise<boolean> {
    try {
      const res = await apiRequest('/api/chat/channels/teaching-groups/order', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel_ids: orderedIds }),
      })
      if (res.ok) {
        await fetchChannels({ force: true })
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] reorderTeachingGroups error:', err)
    }
    return false
  }

  async function inviteChannelMember(channelId: number, userId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
      })
      if (res.ok) {
        await fetchChannels({ force: true })
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] inviteChannelMember error:', err)
    }
    return false
  }

  async function duplicateTeachingGroup(channelId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/duplicate`, { method: 'POST' })
      if (res.ok) {
        await fetchChannels({ force: true })
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] duplicateTeachingGroup error:', err)
    }
    return false
  }

  async function createChannel(payload: {
    name: string
    description?: string | null
    avatar?: string | null
    parent_id?: number | null
  }): Promise<{ ok: boolean; error?: string }> {
    try {
      const res = await apiRequest('/api/chat/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: payload.name.trim(),
          description: payload.description?.trim() || null,
          avatar: payload.avatar?.trim() || null,
          parent_id: payload.parent_id ?? null,
        }),
      })
      if (res.ok) {
        await fetchChannels({ force: true })
        return { ok: true }
      }
      let detail = res.statusText
      try {
        const data = (await res.json()) as { detail?: string }
        if (typeof data.detail === 'string') {
          detail = data.detail
        }
      } catch {
        /* ignore */
      }
      return { ok: false, error: detail }
    } catch (err) {
      console.error('[WorkshopChat] createChannel error:', err)
      return { ok: false, error: err instanceof Error ? err.message : String(err) }
    }
  }

  // ── Topic action helpers ────────────────────────────────────────

  async function moveTopic(
    channelId: number,
    topicId: number,
    targetChannelId: number
  ): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/topics/${topicId}/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_channel_id: targetChannelId }),
      })
      if (res.ok) {
        topics.value = topics.value.filter((t) => t.id !== topicId)
        const scope = getCacheScope()
        if (scope) {
          clearCachedTopics(scope, channelId)
          clearCachedTopics(scope, targetChannelId)
        }
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] moveTopic error:', err)
    }
    return false
  }

  async function renameTopic(channelId: number, topicId: number, title: string): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/topics/${topicId}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      })
      if (res.ok) {
        const data = await res.json()
        const t = topics.value.find((x) => x.id === topicId)
        if (t) t.title = data.title
        const scope = getCacheScope()
        if (scope) {
          clearCachedTopics(scope, channelId)
        }
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] renameTopic error:', err)
    }
    return false
  }

  async function deleteTopic(channelId: number, topicId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/topics/${topicId}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        topics.value = topics.value.filter((t) => t.id !== topicId)
        const scope = getCacheScope()
        if (scope) {
          clearCachedTopics(scope, channelId)
        }
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] deleteTopic error:', err)
    }
    return false
  }

  async function markTopicRead(channelId: number, topicId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/topics/${topicId}/read`, {
        method: 'POST',
      })
      if (res.ok) {
        const t = topics.value.find((x) => x.id === topicId)
        if (t) {
          t.unread_count = 0
        }
        const scope = getCacheScope()
        if (scope) {
          clearCachedTopics(scope, channelId)
        }
        await fetchChannels({ force: true })
      }
      return res.ok
    } catch (err) {
      console.error('[WorkshopChat] markTopicRead error:', err)
    }
    return false
  }

  async function setTopicVisibility(
    channelId: number,
    topicId: number,
    policy: string
  ): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/topics/${topicId}/visibility`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visibility_policy: policy }),
      })
      if (res.ok) {
        const data = await res.json()
        const t = topics.value.find((x) => x.id === topicId)
        if (t) t.visibility_policy = data.visibility_policy
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] setTopicVisibility error:', err)
    }
    return false
  }

  function addIncomingChannelMessage(msg: ChatMessage): void {
    if (msg.channel_id === currentChannelId.value && !msg.topic_id) {
      channelMessages.value.push(msg)
    }
    const ch = channels.value.find((c) => c.id === msg.channel_id)
    if (ch && msg.channel_id !== currentChannelId.value) {
      ch.unread_count += 1
    }
  }

  function addIncomingTopicMessage(msg: ChatMessage): void {
    if (!msg.topic_id) {
      return
    }
    if (msg.topic_id === currentTopicId.value && msg.channel_id === currentChannelId.value) {
      topicMessages.value.push(msg)
      return
    }
    const ch = channels.value.find((c) => c.id === msg.channel_id)
    if (ch) {
      ch.unread_count += 1
    }
    const t = topics.value.find((x) => x.id === msg.topic_id)
    if (t) {
      t.unread_count = (t.unread_count ?? 0) + 1
      t.message_count += 1
    }
  }

  function addIncomingDM(msg: DirectMessageItem): void {
    if (
      msg.sender_id === currentDMPartnerId.value ||
      msg.recipient_id === currentDMPartnerId.value
    ) {
      dmMessages.value.push(msg)
    }
    const conv = dmConversations.value.find(
      (c) => c.partner_id === msg.sender_id || c.partner_id === msg.recipient_id
    )
    if (conv) {
      conv.last_message = {
        content: msg.content.slice(0, 100),
        created_at: msg.created_at,
        is_mine: false,
      }
      if (msg.sender_id !== currentDMPartnerId.value) {
        conv.unread_count += 1
      }
    }
  }

  function setTyping(key: string, username: string): void {
    const existing = typingUsers.value.get(key)
    if (existing) clearTimeout(existing.timeout)
    const timeout = setTimeout(() => typingUsers.value.delete(key), 5000)
    typingUsers.value.set(key, { username, timeout })
  }

  function updatePresence(userId: number, status: string): void {
    const online = new Set(onlineUserIds.value)
    if (status === 'offline') {
      if (online.has(userId)) {
        lastSeenOnlineAtByUserId.value = {
          ...lastSeenOnlineAtByUserId.value,
          [userId]: Date.now(),
        }
        persistLastSeenOnlineIfNeeded()
      }
      online.delete(userId)
    } else {
      online.add(userId)
      if (lastSeenOnlineAtByUserId.value[userId] !== undefined) {
        const next = { ...lastSeenOnlineAtByUserId.value }
        delete next[userId]
        lastSeenOnlineAtByUserId.value = next
        persistLastSeenOnlineIfNeeded()
      }
    }
    onlineUserIds.value = online
  }

  function updateTopic(topicData: ChatTopic): void {
    const idx = topics.value.findIndex((t) => t.id === topicData.id)
    if (idx >= 0) {
      const prev = topics.value[idx]
      topics.value[idx] = {
        ...prev,
        ...topicData,
        unread_count: topicData.unread_count ?? prev.unread_count ?? 0,
        message_count: topicData.message_count ?? prev.message_count ?? 0,
      }
    } else {
      topics.value.unshift({
        ...topicData,
        description: topicData.description ?? null,
        creator_name: topicData.creator_name ?? null,
        visibility_policy: topicData.visibility_policy ?? 'inherit',
        message_count: topicData.message_count ?? 0,
        unread_count: topicData.unread_count ?? 0,
        updated_at: topicData.updated_at ?? topicData.created_at,
      })
    }
  }

  async function toggleReaction(
    messageId: number,
    emojiName: string,
    emojiCode: string
  ): Promise<void> {
    try {
      const res = await apiRequest(`/api/chat/messages/${messageId}/reactions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ emoji_name: emojiName, emoji_code: emojiCode }),
      })
      if (res.ok) {
        const data = await res.json()
        const current = messageReactions.value.get(messageId) ?? []
        if (data.action === 'added') {
          const group = current.find((r) => r.emoji_name === emojiName)
          if (group) {
            group.count += 1
            group.user_ids.push(data.user_id)
            group.reacted = true
          } else {
            current.push({
              emoji_name: emojiName,
              emoji_code: emojiCode,
              count: 1,
              user_ids: [data.user_id],
              reacted: true,
            })
          }
        } else {
          const group = current.find((r) => r.emoji_name === emojiName)
          if (group) {
            group.count -= 1
            group.user_ids = group.user_ids.filter((id) => id !== data.user_id)
            group.reacted = false
            if (group.count <= 0) {
              const idx = current.indexOf(group)
              current.splice(idx, 1)
            }
          }
        }
        messageReactions.value.set(messageId, [...current])
      }
    } catch (err) {
      console.error('[WorkshopChat] toggleReaction error:', err)
    }
  }

  async function toggleStar(messageId: number): Promise<void> {
    try {
      const res = await apiRequest(`/api/chat/messages/${messageId}/star`, {
        method: 'POST',
      })
      if (res.ok) {
        const data = await res.json()
        if (data.action === 'starred') {
          starredMessageIds.value.add(messageId)
        } else {
          starredMessageIds.value.delete(messageId)
        }
      }
    } catch (err) {
      console.error('[WorkshopChat] toggleStar error:', err)
    }
  }

  async function fetchReactionsBatch(messageIds: number[]): Promise<void> {
    if (messageIds.length === 0) return
    try {
      const idsParam = messageIds.join(',')
      const res = await apiRequest(`/api/chat/messages/reactions/batch?ids=${idsParam}`)
      if (res.ok) {
        const data: Record<string, ReactionGroup[]> = await res.json()
        for (const [idStr, groups] of Object.entries(data)) {
          messageReactions.value.set(Number(idStr), groups)
        }
      }
    } catch {
      /* batch fetch is best-effort */
    }
  }

  async function fetchStarredBatch(messageIds: number[]): Promise<void> {
    if (messageIds.length === 0) return
    try {
      const idsParam = messageIds.join(',')
      const res = await apiRequest(`/api/chat/messages/starred/batch?ids=${idsParam}`)
      if (res.ok) {
        const data: number[] = await res.json()
        for (const id of data) {
          starredMessageIds.value.add(id)
        }
      }
    } catch {
      /* batch fetch is best-effort */
    }
  }

  async function fetchAttachmentsBatch(messageIds: number[]): Promise<void> {
    if (messageIds.length === 0) return
    try {
      const idsParam = messageIds.join(',')
      const res = await apiRequest(`/api/chat/messages/attachments/batch?ids=${idsParam}`)
      if (res.ok) {
        const data: Record<string, FileAttachment[]> = await res.json()
        for (const [idStr, atts] of Object.entries(data)) {
          messageAttachments.value.set(Number(idStr), atts)
        }
      }
    } catch {
      /* batch fetch is best-effort */
    }
  }

  function getReactionsForMessage(messageId: number): ReactionGroup[] {
    return messageReactions.value.get(messageId) ?? []
  }

  function isMessageStarred(messageId: number): boolean {
    return starredMessageIds.value.has(messageId)
  }

  function getAttachmentsForMessage(messageId: number): FileAttachment[] {
    return messageAttachments.value.get(messageId) ?? []
  }

  function handleReactionUpdate(
    messageId: number,
    emojiName: string,
    emojiCode: string,
    userId: number,
    action: string
  ): void {
    const current = messageReactions.value.get(messageId) ?? []
    if (action === 'added') {
      const group = current.find((r) => r.emoji_name === emojiName)
      if (group) {
        if (!group.user_ids.includes(userId)) {
          group.count += 1
          group.user_ids.push(userId)
        }
      } else {
        current.push({
          emoji_name: emojiName,
          emoji_code: emojiCode,
          count: 1,
          user_ids: [userId],
          reacted: false,
        })
      }
    } else {
      const group = current.find((r) => r.emoji_name === emojiName)
      if (group) {
        group.count -= 1
        group.user_ids = group.user_ids.filter((id) => id !== userId)
        if (group.count <= 0) {
          const idx = current.indexOf(group)
          current.splice(idx, 1)
        }
      }
    }
    messageReactions.value.set(messageId, [...current])
  }

  function leaveWorkshopHomeView(): void {
    workshopHomeViewActive.value = false
  }

  function openWorkshopInboxHome(): void {
    workshopHomeViewActive.value = true
    showChannelBrowser.value = false
    mainChannelFeedActive.value = false
    teachingGroupLandingId.value = null
    currentChannelId.value = null
    currentTopicId.value = null
    currentDMPartnerId.value = null
    channelMessages.value = []
    topicMessages.value = []
    topics.value = []
    dmMessages.value = []
  }

  async function openTeachingGroupLanding(groupId: number): Promise<void> {
    workshopHomeViewActive.value = false
    showChannelBrowser.value = false
    currentDMPartnerId.value = null
    mainChannelFeedActive.value = false
    currentChannelId.value = null
    currentTopicId.value = null
    channelMessages.value = []
    topicMessages.value = []
    topics.value = []
    teachingGroupLandingId.value = groupId
    const group = findChannelById(groupId)
    const children = group?.children ?? []
    await Promise.all(children.map((c) => fetchTopics(c.id, { merge: true })))
  }

  function openMainChannelFeed(): void {
    workshopHomeViewActive.value = false
    showChannelBrowser.value = false
    currentDMPartnerId.value = null
    mainChannelFeedActive.value = true
    currentTopicId.value = null
    topicMessages.value = []
  }

  function leaveMainChannelFeed(): void {
    mainChannelFeedActive.value = false
  }

  function selectChannel(channelId: number | null): void {
    teachingGroupLandingId.value = null
    if (channelId !== null) {
      workshopHomeViewActive.value = false
    }
    mainChannelFeedActive.value = false
    currentChannelId.value = channelId
    currentTopicId.value = null
    channelMessages.value = []
    topicMessages.value = []
    topics.value = []
  }

  function selectTopic(topicId: number | null): void {
    if (topicId !== null) {
      workshopHomeViewActive.value = false
    }
    mainChannelFeedActive.value = false
    currentTopicId.value = topicId
    topicMessages.value = []
  }

  function selectDMPartner(partnerId: number | null): void {
    if (partnerId !== null) {
      workshopHomeViewActive.value = false
    }
    teachingGroupLandingId.value = null
    currentDMPartnerId.value = partnerId
    dmMessages.value = []
  }

  function openCreateChannel(opts?: { parentId: number | null }): void {
    createChannelPrefillParentId.value = opts?.parentId ?? null
    createChannelDialogVisible.value = true
  }

  function closeCreateChannelDialog(): void {
    createChannelDialogVisible.value = false
    createChannelPrefillParentId.value = null
  }

  function requestNewTopicForChannel(channelId: number): void {
    newTopicDialogRequestChannelId.value = channelId
  }

  function clearNewTopicDialogRequest(): void {
    newTopicDialogRequestChannelId.value = null
  }

  function reset(userIdOverride?: string): void {
    clearWorkshopListInflight()
    const auth = useAuthStore()
    const uid = userIdOverride ?? auth.user?.id
    if (uid) {
      clearWorkshopChatCachesForUser(uid)
    }
    channels.value = []
    currentChannelId.value = null
    currentTopicId.value = null
    currentDMPartnerId.value = null
    topics.value = []
    channelMessages.value = []
    topicMessages.value = []
    dmConversations.value = []
    dmMessages.value = []
    channelMembers.value = []
    orgMembers.value = []
    orgMembersTotal.value = 0
    orgMembersListQuery.value = ''
    adminOrgs.value = []
    adminOrgId.value = null
    activeTab.value = 'channels'
    onlineUserIds.value = new Set()
    lastSeenOnlineAtByUserId.value = {}
    typingUsers.value.clear()
    messageReactions.value.clear()
    starredMessageIds.value.clear()
    messageAttachments.value.clear()
    showChannelBrowser.value = false
    workshopHomeViewActive.value = false
    mainChannelFeedActive.value = false
    dialogChannelSettingsId.value = null
    dialogTopicEdit.value = null
    createChannelDialogVisible.value = false
    createChannelPrefillParentId.value = null
    newTopicDialogRequestChannelId.value = null
    teachingGroupLandingId.value = null
  }

  registerWorkshopChatResetOnAuthClear((userId) => {
    reset(userId)
  })

  return {
    channels,
    currentChannelId,
    currentTopicId,
    currentDMPartnerId,
    topics,
    channelMessages,
    topicMessages,
    dmConversations,
    dmMessages,
    channelMembers,
    activeTab,
    onlineUserIds,
    lastSeenOnlineAtByUserId,
    hydrateLastSeenOnlineFromStorage,
    typingUsers,
    loading,
    currentChannel,
    topicParticipantIds,
    joinedChannels,
    totalUnreadChannels,
    totalUnreadDMs,
    initializeDefaults,
    fetchChannels,
    fetchTopics,
    fetchChannelMessages,
    fetchTopicMessages,
    fetchDMConversations,
    fetchDMMessages,
    searchChannelMessages,
    searchTopicMessages,
    searchDMMessages,
    fetchChannelMembers,
    fetchOrgMembers,
    searchOrgMembers,
    fetchAdminOrgs,
    setAdminOrgId,
    orgMembers,
    orgMembersTotal,
    orgMembersHasMore,
    orgMembersListQuery,
    adminOrgs,
    adminOrgId,
    joinChannel,
    leaveChannel,
    archiveChannel,
    addIncomingChannelMessage,
    addIncomingTopicMessage,
    addIncomingDM,
    setTyping,
    updatePresence,
    updateTopic,
    selectChannel,
    selectTopic,
    selectDMPartner,
    reset,
    messageReactions,
    starredMessageIds,
    messageAttachments,
    toggleReaction,
    toggleStar,
    fetchReactionsBatch,
    fetchStarredBatch,
    fetchAttachmentsBatch,
    getReactionsForMessage,
    isMessageStarred,
    getAttachmentsForMessage,
    handleReactionUpdate,
    announceChannels,
    publicChannels,
    privateChannels,
    pinnedChannels,
    channelGroups,
    allLessonStudies,
    findChannelById,
    findParentGroup,
    toggleChannelMute,
    toggleChannelPin,
    markChannelReadAll,
    markDMPartnerRead,
    updateChannelLessonStudy,
    updateChannelPrefs,
    updateChannelPermissions,
    updateChannelDetails,
    reorderTeachingGroups,
    inviteChannelMember,
    duplicateTeachingGroup,
    createChannel,
    moveTopic,
    renameTopic,
    deleteTopic,
    markTopicRead,
    setTopicVisibility,
    showChannelBrowser,
    workshopHomeViewActive,
    mainChannelFeedActive,
    openMainChannelFeed,
    leaveMainChannelFeed,
    openWorkshopInboxHome,
    leaveWorkshopHomeView,
    dialogChannelSettingsId,
    dialogTopicEdit,
    createChannelDialogVisible,
    createChannelPrefillParentId,
    newTopicDialogRequestChannelId,
    openCreateChannel,
    closeCreateChannelDialog,
    requestNewTopicForChannel,
    clearNewTopicDialogRequest,
    teachingGroupLandingId,
    openTeachingGroupLanding,
  }
})
