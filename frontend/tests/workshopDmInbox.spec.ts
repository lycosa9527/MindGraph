import { describe, expect, it } from 'vitest'

import type { DirectMessageItem, DMConversation } from '@/stores/workshopChat'
import { workshopDmRouteQuery } from '@/utils/workshopChatNavigate'
import { isWorkshopChatPath } from '@/utils/workshopChatRoute'
import {
  applyIncomingDm,
  dmCounterpartyId,
  ensureDmConversation,
  firstRealPersonName,
  isNumericUserFallback,
  resolveDmPersonName,
} from '@/utils/workshopDmInbox'

function dm(partial: Partial<DirectMessageItem> & Pick<DirectMessageItem, 'id'>): DirectMessageItem {
  return {
    sender_id: 9,
    sender_name: '林老师',
    sender_avatar: '🐱',
    recipient_id: 2,
    content: 'hello',
    message_type: 'text',
    is_read: false,
    created_at: '2026-09-14T00:00:00Z',
    edited_at: null,
    ...partial,
  }
}

describe('workshopDmInbox names', () => {
  it('treats User <id> as a placeholder, not a display name', () => {
    expect(isNumericUserFallback('User 9')).toBe(true)
    expect(isNumericUserFallback('  User 12 ')).toBe(true)
    expect(isNumericUserFallback('林老师')).toBe(false)
    expect(isNumericUserFallback('')).toBe(true)
  })

  it('prefers a real name over a sender-id fallback', () => {
    expect(firstRealPersonName('User 9', '林老师')).toBe('林老师')
    expect(resolveDmPersonName(9, 'User 9', undefined, '王老师')).toBe('王老师')
    expect(resolveDmPersonName(9)).toBe('User 9')
  })
})

describe('workshopDmInbox conversations', () => {
  it('resolves the other party from either direction', () => {
    expect(dmCounterpartyId({ sender_id: 9, recipient_id: 2 }, 2)).toBe(9)
    expect(dmCounterpartyId({ sender_id: 2, recipient_id: 9 }, 2)).toBe(9)
  })

  it('creates a named conversation on a first incoming DM', () => {
    const conversations: DMConversation[] = []
    const messages: DirectMessageItem[] = []
    const result = applyIncomingDm({
      msg: dm({ id: 3 }),
      myId: 2,
      currentPartnerId: null,
      conversations,
      messages,
    })
    expect(result.isMine).toBe(false)
    expect(result.viewingOpenThread).toBe(false)
    expect(messages).toHaveLength(0)
    expect(conversations).toHaveLength(1)
    expect(conversations[0].partner_id).toBe(9)
    expect(conversations[0].partner_name).toBe('林老师')
    expect(conversations[0].unread_count).toBe(0)
    expect(conversations[0].last_message.content).toBe('hello')
  })

  it('appends to the open thread and keeps the partner name', () => {
    const conversations: DMConversation[] = []
    const messages: DirectMessageItem[] = []
    const result = applyIncomingDm({
      msg: dm({ id: 4 }),
      myId: 2,
      currentPartnerId: 9,
      conversations,
      messages,
    })
    expect(result.viewingOpenThread).toBe(true)
    expect(messages).toHaveLength(1)
    expect(conversations[0].partner_name).toBe('林老师')
  })

  it('replaces a User <id> label when a real name arrives', () => {
    const conversations: DMConversation[] = []
    ensureDmConversation(conversations, 9, 'User 9', null)
    expect(conversations[0].partner_name).toBe('User 9')
    ensureDmConversation(conversations, 9, '林老师', '🐱')
    expect(conversations[0].partner_name).toBe('林老师')
    expect(conversations[0].partner_avatar).toBe('🐱')
  })
})

describe('workshop DM navigation', () => {
  it('pushes ?dm= so inbox sync cannot wipe the narrow', () => {
    expect(workshopDmRouteQuery(7)).toEqual({ dm: '7' })
    expect(isWorkshopChatPath('/workshop-chat')).toBe(true)
    expect(isWorkshopChatPath('/workshop-chat/')).toBe(true)
    expect(isWorkshopChatPath('/canvas')).toBe(false)
  })
})
