/**
 * 1:1 DM inbox helpers — partner identity, display names, conversation upsert.
 *
 * Notifications and the sidebar must use a person's name, not a raw user id.
 * Incoming frames also have to create the conversation row (Zulip-style) so a
 * first DM is visible without a refresh.
 */
import type { DirectMessageItem, DMConversation, OrgMember } from '@/stores/workshopChat'

const PLACEHOLDER_USER_LABEL = /^User \s*\d+$/i

export function dmCounterpartyId(
  msg: Pick<DirectMessageItem, 'sender_id' | 'recipient_id'>,
  myId: number
): number {
  return msg.sender_id === myId ? msg.recipient_id : msg.sender_id
}

export function isNumericUserFallback(name: string | null | undefined): boolean {
  if (name == null) return true
  const trimmed = name.trim()
  if (!trimmed) return true
  return PLACEHOLDER_USER_LABEL.test(trimmed)
}

export function firstRealPersonName(
  ...candidates: Array<string | null | undefined>
): string | null {
  for (const candidate of candidates) {
    if (candidate != null && !isNumericUserFallback(candidate)) {
      return candidate.trim()
    }
  }
  return null
}

export function resolveDmPersonName(
  userId: number,
  ...candidates: Array<string | null | undefined>
): string {
  return firstRealPersonName(...candidates) ?? `User ${userId}`
}

export function orgMemberById(
  members: Pick<OrgMember, 'id' | 'name' | 'avatar'>[],
  userId: number
): Pick<OrgMember, 'id' | 'name' | 'avatar'> | undefined {
  return members.find((row) => row.id === userId)
}

export function ensureDmConversation(
  conversations: DMConversation[],
  partnerId: number,
  name?: string | null,
  avatar?: string | null
): DMConversation {
  const existing = conversations.find((row) => row.partner_id === partnerId)
  const resolvedName = firstRealPersonName(name)
  if (existing) {
    if (resolvedName && isNumericUserFallback(existing.partner_name)) {
      existing.partner_name = resolvedName
    }
    if (avatar && !existing.partner_avatar) {
      existing.partner_avatar = avatar
    }
    return existing
  }
  const created: DMConversation = {
    partner_id: partnerId,
    partner_name: resolvedName ?? `User ${partnerId}`,
    partner_avatar: avatar ?? null,
    last_message: { content: null, created_at: null, is_mine: false },
    unread_count: 0,
  }
  conversations.unshift(created)
  return created
}

export interface ApplyIncomingDmResult {
  /** True when the open 研习社 DM thread received this row (mark-read eligible). */
  viewingOpenThread: boolean
  isMine: boolean
}

export function applyIncomingDm(params: {
  msg: DirectMessageItem
  myId: number
  currentPartnerId: number | null
  conversations: DMConversation[]
  messages: DirectMessageItem[]
  directoryName?: string | null
  directoryAvatar?: string | null
}): ApplyIncomingDmResult {
  const { msg, myId, currentPartnerId, conversations, messages } = params
  const isMine = Number.isFinite(myId) && msg.sender_id === myId
  if (messages.some((row) => row.id === msg.id)) {
    return { viewingOpenThread: false, isMine }
  }

  const viewingOpenThread =
    currentPartnerId != null &&
    (msg.sender_id === currentPartnerId || msg.recipient_id === currentPartnerId)

  if (viewingOpenThread) {
    messages.push(msg)
  }

  const partnerId = dmCounterpartyId(msg, myId)
  const partnerIsSender = partnerId === msg.sender_id
  const incomingName = partnerIsSender
    ? firstRealPersonName(msg.sender_name, params.directoryName)
    : firstRealPersonName(params.directoryName)
  const incomingAvatar = partnerIsSender
    ? (msg.sender_avatar ?? params.directoryAvatar ?? null)
    : (params.directoryAvatar ?? null)

  const conv = ensureDmConversation(
    conversations,
    partnerId,
    incomingName,
    incomingAvatar
  )
  conv.last_message = {
    content: msg.content.slice(0, 100),
    created_at: msg.created_at,
    is_mine: isMine,
  }
  return { viewingOpenThread, isMine }
}
