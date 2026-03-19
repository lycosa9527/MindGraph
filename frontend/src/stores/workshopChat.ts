/**
 * Workshop Chat Pinia Store
 *
 * Central state management for channels, topics, DMs, unread counts, and presence.
 * Works with useWorkshopChat composable for WebSocket integration.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { apiRequest } from '@/utils/apiClient'

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
  unread_count: number
  created_at: string
  parent_id: number | null
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
  created_at: string
  updated_at: string
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
}

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
  const idleUserIds = ref<Set<number>>(new Set())
  const typingUsers = ref<Map<string, { username: string; timeout: ReturnType<typeof setTimeout> }>>(new Map())

  const loading = ref(false)

  const orgMembers = ref<OrgMember[]>([])
  const adminOrgs = ref<AdminOrg[]>([])
  const adminOrgId = ref<number | null>(null)

  const messageReactions = ref<Map<number, ReactionGroup[]>>(new Map())
  const starredMessageIds = ref<Set<number>>(new Set())
  const messageAttachments = ref<Map<number, FileAttachment[]>>(new Map())

  const showChannelBrowser = ref(false)
  const dialogChannelSettingsId = ref<number | null>(null)
  const dialogTopicEdit = ref<{
    topicId: number
    channelId: number
    mode: 'rename' | 'move'
  } | null>(null)

  const currentChannel = computed(() => {
    if (currentChannelId.value === null) return null
    return findChannelById(currentChannelId.value)
  })

  const topicParticipantIds = computed<Set<number>>(() => {
    const ids = new Set<number>()
    const msgs = currentTopicId.value
      ? topicMessages.value
      : channelMessages.value
    for (const msg of msgs) {
      ids.add(msg.sender_id)
    }
    return ids
  })

  const joinedChannels = computed(() =>
    channels.value.filter(c => c.is_joined),
  )

  const totalUnreadChannels = computed(() =>
    channels.value.reduce((sum, c) => sum + (c.is_joined ? c.unread_count : 0), 0),
  )

  const totalUnreadDMs = computed(() =>
    dmConversations.value.reduce((sum, c) => sum + c.unread_count, 0),
  )

  const announceChannels = computed(() =>
    channels.value.filter(c => c.channel_type === 'announce'),
  )

  const publicChannels = computed(() =>
    channels.value.filter(c => c.channel_type === 'public'),
  )

  const privateChannels = computed(() =>
    channels.value.filter(c => c.channel_type === 'private'),
  )

  const pinnedChannels = computed(() =>
    channels.value.filter(c => c.pin_to_top && c.is_joined),
  )

  const channelGroups = computed(() =>
    channels.value.filter(
      c => c.parent_id === null || c.parent_id === undefined,
    ),
  )

  const allLessonStudies = computed(() =>
    channels.value.flatMap(g => g.children ?? []),
  )

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

  async function fetchChannels(): Promise<void> {
    try {
      const orgParam = adminOrgId.value ? `?org_id=${adminOrgId.value}` : ''
      const res = await apiRequest(`/api/chat/channels${orgParam}`)
      if (res.ok) {
        channels.value = await res.json()
      }
    } catch (err) {
      console.error('[WorkshopChat] fetchChannels error:', err)
    }
  }

  async function fetchTopics(channelId: number): Promise<void> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/topics`)
      if (res.ok) {
        topics.value = await res.json()
      }
    } catch (err) {
      console.error('[WorkshopChat] fetchTopics error:', err)
    }
  }

  async function fetchChannelMessages(
    channelId: number, anchor = 0, numBefore = 50,
  ): Promise<ChatMessage[]> {
    try {
      const res = await apiRequest(
        `/api/chat/channels/${channelId}/messages?anchor=${anchor}&num_before=${numBefore}`,
      )
      if (res.ok) {
        const msgs: ChatMessage[] = await res.json()
        if (anchor === 0) {
          channelMessages.value = msgs
        } else {
          channelMessages.value = [...msgs, ...channelMessages.value]
        }
        return msgs
      }
    } catch (err) {
      console.error('[WorkshopChat] fetchChannelMessages error:', err)
    }
    return []
  }

  async function fetchTopicMessages(
    channelId: number, topicId: number, anchor = 0, numBefore = 50,
  ): Promise<ChatMessage[]> {
    try {
      const res = await apiRequest(
        `/api/chat/channels/${channelId}/topics/${topicId}/messages?anchor=${anchor}&num_before=${numBefore}`,
      )
      if (res.ok) {
        const msgs: ChatMessage[] = await res.json()
        if (anchor === 0) {
          topicMessages.value = msgs
        } else {
          topicMessages.value = [...msgs, ...topicMessages.value]
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
    partnerId: number, anchor = 0, numBefore = 50,
  ): Promise<DirectMessageItem[]> {
    try {
      const res = await apiRequest(
        `/api/chat/dm/${partnerId}/messages?anchor=${anchor}&num_before=${numBefore}`,
      )
      if (res.ok) {
        const msgs: DirectMessageItem[] = await res.json()
        if (anchor === 0) {
          dmMessages.value = msgs
        } else {
          dmMessages.value = [...msgs, ...dmMessages.value]
        }
        return msgs
      }
    } catch (err) {
      console.error('[WorkshopChat] fetchDMMessages error:', err)
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

  async function fetchOrgMembers(): Promise<void> {
    try {
      const orgParam = adminOrgId.value ? `?org_id=${adminOrgId.value}` : ''
      const res = await apiRequest(`/api/chat/org-members${orgParam}`)
      if (res.ok) {
        orgMembers.value = await res.json()
      }
    } catch (err) {
      console.error('[WorkshopChat] fetchOrgMembers error:', err)
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

  function setAdminOrgId(orgId: number | null): void {
    adminOrgId.value = orgId
  }

  async function joinChannel(channelId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/join`, { method: 'POST' })
      if (res.ok) {
        await fetchChannels()
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
        await fetchChannels()
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] leaveChannel error:', err)
    }
    return false
  }

  // ── Channel subscription helpers ──────────────────────────────

  async function toggleChannelMute(channelId: number): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/mute`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        const ch = channels.value.find(c => c.id === channelId)
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
        const ch = channels.value.find(c => c.id === channelId)
        if (ch) ch.pin_to_top = data.pin_to_top
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] toggleChannelPin error:', err)
    }
    return false
  }

  async function updateChannelPrefs(
    channelId: number,
    prefs: { color?: string; desktop_notifications?: boolean; email_notifications?: boolean },
  ): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/preferences`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(prefs),
      })
      if (res.ok) {
        const data = await res.json()
        const ch = channels.value.find(c => c.id === channelId)
        if (ch) ch.color = data.color
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] updateChannelPrefs error:', err)
    }
    return false
  }

  async function updateChannelPermissions(
    channelId: number,
    perms: { channel_type?: string; posting_policy?: string; is_default?: boolean },
  ): Promise<boolean> {
    try {
      const res = await apiRequest(`/api/chat/channels/${channelId}/permissions`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(perms),
      })
      if (res.ok) {
        await fetchChannels()
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] updateChannelPermissions error:', err)
    }
    return false
  }

  // ── Topic action helpers ────────────────────────────────────────

  async function moveTopic(
    channelId: number, topicId: number, targetChannelId: number,
  ): Promise<boolean> {
    try {
      const res = await apiRequest(
        `/api/chat/channels/${channelId}/topics/${topicId}/move`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_channel_id: targetChannelId }),
        },
      )
      if (res.ok) {
        topics.value = topics.value.filter(t => t.id !== topicId)
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] moveTopic error:', err)
    }
    return false
  }

  async function renameTopic(
    channelId: number, topicId: number, title: string,
  ): Promise<boolean> {
    try {
      const res = await apiRequest(
        `/api/chat/channels/${channelId}/topics/${topicId}/rename`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title }),
        },
      )
      if (res.ok) {
        const data = await res.json()
        const t = topics.value.find(x => x.id === topicId)
        if (t) t.title = data.title
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] renameTopic error:', err)
    }
    return false
  }

  async function deleteTopic(channelId: number, topicId: number): Promise<boolean> {
    try {
      const res = await apiRequest(
        `/api/chat/channels/${channelId}/topics/${topicId}`, { method: 'DELETE' },
      )
      if (res.ok) {
        topics.value = topics.value.filter(t => t.id !== topicId)
        return true
      }
    } catch (err) {
      console.error('[WorkshopChat] deleteTopic error:', err)
    }
    return false
  }

  async function markTopicRead(channelId: number, topicId: number): Promise<boolean> {
    try {
      const res = await apiRequest(
        `/api/chat/channels/${channelId}/topics/${topicId}/read`, { method: 'POST' },
      )
      return res.ok
    } catch (err) {
      console.error('[WorkshopChat] markTopicRead error:', err)
    }
    return false
  }

  async function setTopicVisibility(
    channelId: number, topicId: number, policy: string,
  ): Promise<boolean> {
    try {
      const res = await apiRequest(
        `/api/chat/channels/${channelId}/topics/${topicId}/visibility`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ visibility_policy: policy }),
        },
      )
      if (res.ok) {
        const data = await res.json()
        const t = topics.value.find(x => x.id === topicId)
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
    const ch = channels.value.find(c => c.id === msg.channel_id)
    if (ch && msg.channel_id !== currentChannelId.value) {
      ch.unread_count += 1
    }
  }

  function addIncomingTopicMessage(msg: ChatMessage): void {
    if (msg.topic_id === currentTopicId.value) {
      topicMessages.value.push(msg)
    }
  }

  function addIncomingDM(msg: DirectMessageItem): void {
    if (
      msg.sender_id === currentDMPartnerId.value
      || msg.recipient_id === currentDMPartnerId.value
    ) {
      dmMessages.value.push(msg)
    }
    const conv = dmConversations.value.find(
      c => c.partner_id === msg.sender_id || c.partner_id === msg.recipient_id,
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
    if (status === 'offline') {
      onlineUserIds.value.delete(userId)
      idleUserIds.value.delete(userId)
    } else if (status === 'idle') {
      onlineUserIds.value.delete(userId)
      idleUserIds.value.add(userId)
    } else {
      onlineUserIds.value.add(userId)
      idleUserIds.value.delete(userId)
    }
  }

  function updateTopic(topicData: ChatTopic): void {
    const idx = topics.value.findIndex(t => t.id === topicData.id)
    if (idx >= 0) {
      topics.value[idx] = topicData
    } else {
      topics.value.unshift(topicData)
    }
  }

  async function toggleReaction(
    messageId: number, emojiName: string, emojiCode: string,
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
          const group = current.find(r => r.emoji_name === emojiName)
          if (group) {
            group.count += 1
            group.user_ids.push(data.user_id)
            group.reacted = true
          } else {
            current.push({
              emoji_name: emojiName, emoji_code: emojiCode,
              count: 1, user_ids: [data.user_id], reacted: true,
            })
          }
        } else {
          const group = current.find(r => r.emoji_name === emojiName)
          if (group) {
            group.count -= 1
            group.user_ids = group.user_ids.filter(id => id !== data.user_id)
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
      const res = await apiRequest(
        `/api/chat/messages/reactions/batch?ids=${idsParam}`,
      )
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
      const res = await apiRequest(
        `/api/chat/messages/starred/batch?ids=${idsParam}`,
      )
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
      const res = await apiRequest(
        `/api/chat/messages/attachments/batch?ids=${idsParam}`,
      )
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
    messageId: number, emojiName: string, emojiCode: string,
    userId: number, action: string,
  ): void {
    const current = messageReactions.value.get(messageId) ?? []
    if (action === 'added') {
      const group = current.find(r => r.emoji_name === emojiName)
      if (group) {
        if (!group.user_ids.includes(userId)) {
          group.count += 1
          group.user_ids.push(userId)
        }
      } else {
        current.push({
          emoji_name: emojiName, emoji_code: emojiCode,
          count: 1, user_ids: [userId], reacted: false,
        })
      }
    } else {
      const group = current.find(r => r.emoji_name === emojiName)
      if (group) {
        group.count -= 1
        group.user_ids = group.user_ids.filter(id => id !== userId)
        if (group.count <= 0) {
          const idx = current.indexOf(group)
          current.splice(idx, 1)
        }
      }
    }
    messageReactions.value.set(messageId, [...current])
  }

  function selectChannel(channelId: number | null): void {
    currentChannelId.value = channelId
    currentTopicId.value = null
    channelMessages.value = []
    topicMessages.value = []
    topics.value = []
  }

  function selectTopic(topicId: number | null): void {
    currentTopicId.value = topicId
    topicMessages.value = []
  }

  function selectDMPartner(partnerId: number | null): void {
    currentDMPartnerId.value = partnerId
    dmMessages.value = []
  }

  function reset(): void {
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
    adminOrgs.value = []
    adminOrgId.value = null
    activeTab.value = 'channels'
    onlineUserIds.value.clear()
    idleUserIds.value.clear()
    typingUsers.value.clear()
    messageReactions.value.clear()
    starredMessageIds.value.clear()
    messageAttachments.value.clear()
    showChannelBrowser.value = false
    dialogChannelSettingsId.value = null
    dialogTopicEdit.value = null
  }

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
    idleUserIds,
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
    fetchChannelMembers,
    fetchOrgMembers,
    fetchAdminOrgs,
    setAdminOrgId,
    orgMembers,
    adminOrgs,
    adminOrgId,
    joinChannel,
    leaveChannel,
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
    updateChannelPrefs,
    updateChannelPermissions,
    moveTopic,
    renameTopic,
    deleteTopic,
    markTopicRead,
    setTopicVisibility,
    showChannelBrowser,
    dialogChannelSettingsId,
    dialogTopicEdit,
  }
})
