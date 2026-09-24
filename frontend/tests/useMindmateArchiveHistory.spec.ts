import { describe, expect, it } from 'vitest'

import {
  type MindmateArchiveConversation,
  conversationsInFolder,
  groupUncategorizedConversations,
} from '@/composables/sidebar/useMindmateArchiveHistory'

function conversation(
  id: string,
  updatedAt: number,
  extras: Partial<MindmateArchiveConversation> = {}
): MindmateArchiveConversation {
  return { id, updated_at: updatedAt, ...extras }
}

describe('mindmate archive history', () => {
  it('keeps foldered chats out of the uncategorized timeline', () => {
    const nowSec = Math.floor(Date.now() / 1000)
    const groups = groupUncategorizedConversations(
      [
        conversation('today', nowSec),
        conversation('filed', nowSec, { folder_id: 'folder-1' }),
        conversation('pinned', nowSec - 3 * 86400, { is_pinned: true }),
      ],
      { showAll: true }
    )

    expect(groups.today.map((item) => item.id)).toEqual(['today'])
    expect(groups.pinned.map((item) => item.id)).toEqual(['pinned'])
    expect(groups.yesterday).toEqual([])
    expect(groups.week).toEqual([])
    expect(groups.month).toEqual([])
  })

  it('limits the uncategorized window before show-all', () => {
    const nowSec = Math.floor(Date.now() / 1000)
    const items = [0, 1, 2].map((offset) => conversation(`c${offset}`, nowSec - offset))
    const groups = groupUncategorizedConversations(items, { limit: 2 })
    const shown = [
      ...groups.pinned,
      ...groups.today,
      ...groups.yesterday,
      ...groups.week,
      ...groups.month,
    ]
    expect(shown.map((item) => item.id)).toEqual(['c0', 'c1'])
  })

  it('sorts folder contents with pinned chats first', () => {
    const rows = conversationsInFolder(
      [
        conversation('old', 10, { folder_id: 'folder-1' }),
        conversation('pinned', 5, { folder_id: 'folder-1', is_pinned: true }),
        conversation('other', 99, { folder_id: 'folder-2' }),
      ],
      'folder-1'
    )
    expect(rows.map((item) => item.id)).toEqual(['pinned', 'old'])
  })
})
