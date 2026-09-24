/**
 * Grouping helpers for MindMate conversation folders.
 * Time buckets match saved-diagram archive history.
 */
import { type ComputedRef, type MaybeRefOrGetter, type Ref, computed, ref, toValue } from 'vue'

const COLLAPSED_STORAGE_KEY = 'mindgraph:mindmate-archive:collapsed'

export interface MindmateArchiveConversation {
  id: string
  updated_at: number
  is_pinned?: boolean
  folder_id?: string | null
}

export interface TimeGroupedConversations<T> {
  pinned: T[]
  today: T[]
  yesterday: T[]
  week: T[]
  month: T[]
}

export const MINDMATE_TIME_GROUP_KEYS = ['pinned', 'today', 'yesterday', 'week', 'month'] as const

export type MindmateTimeGroupKey = (typeof MINDMATE_TIME_GROUP_KEYS)[number]

function loadCollapsedFolderIds(): Set<string> {
  try {
    const raw = sessionStorage.getItem(COLLAPSED_STORAGE_KEY)
    if (!raw) return new Set()
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return new Set()
    return new Set(parsed.filter((id): id is string => typeof id === 'string'))
  } catch {
    return new Set()
  }
}

function persistCollapsedFolderIds(collapsed: Set<string>): void {
  try {
    sessionStorage.setItem(COLLAPSED_STORAGE_KEY, JSON.stringify([...collapsed]))
  } catch {
    // ignore quota / private mode
  }
}

export function conversationsInFolder<T extends MindmateArchiveConversation>(
  conversations: T[],
  folderId: string
): T[] {
  return conversations
    .filter((conversation) => conversation.folder_id === folderId)
    .sort((a, b) => {
      if (Boolean(a.is_pinned) !== Boolean(b.is_pinned)) {
        return a.is_pinned ? -1 : 1
      }
      return b.updated_at - a.updated_at
    })
}

export function groupUncategorizedConversations<T extends MindmateArchiveConversation>(
  conversations: T[],
  options: { limit?: number; showAll?: boolean } = {}
): TimeGroupedConversations<T> {
  const groups: TimeGroupedConversations<T> = {
    pinned: [],
    today: [],
    yesterday: [],
    week: [],
    month: [],
  }

  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterdayStart = todayStart - 24 * 60 * 60 * 1000
  const weekStart = todayStart - 7 * 24 * 60 * 60 * 1000

  const uncategorized = conversations.filter((conversation) => !conversation.folder_id)
  const limit = options.showAll ? uncategorized.length : (options.limit ?? uncategorized.length)
  const items = uncategorized.slice(0, limit)

  items.forEach((conversation) => {
    if (conversation.is_pinned) {
      groups.pinned.push(conversation)
      return
    }

    const convTime = conversation.updated_at * 1000
    if (convTime >= todayStart) {
      groups.today.push(conversation)
    } else if (convTime >= yesterdayStart) {
      groups.yesterday.push(conversation)
    } else if (convTime >= weekStart) {
      groups.week.push(conversation)
    } else {
      groups.month.push(conversation)
    }
  })

  return groups
}

export function useMindmateArchiveHistory<T extends MindmateArchiveConversation>(
  conversations: Ref<T[]> | ComputedRef<T[]>,
  initialLimit: MaybeRefOrGetter<number> = 10
) {
  const showAllUncategorized = ref(false)
  const collapsedFolders = ref<Set<string>>(loadCollapsedFolderIds())

  const uncategorizedConversations = computed(() =>
    conversations.value.filter((conversation) => !conversation.folder_id)
  )

  const groupedUncategorized = computed(() =>
    groupUncategorizedConversations(conversations.value, {
      limit: toValue(initialLimit),
      showAll: showAllUncategorized.value,
    })
  )

  const hasMoreUncategorized = computed(
    () =>
      uncategorizedConversations.value.length > toValue(initialLimit) && !showAllUncategorized.value
  )

  const remainingUncategorizedCount = computed(
    () => uncategorizedConversations.value.length - toValue(initialLimit)
  )

  function isFolderCollapsed(folderId: string): boolean {
    return collapsedFolders.value.has(folderId)
  }

  function toggleFolderCollapsed(folderId: string): void {
    const next = new Set(collapsedFolders.value)
    if (next.has(folderId)) {
      next.delete(folderId)
    } else {
      next.add(folderId)
    }
    collapsedFolders.value = next
    persistCollapsedFolderIds(next)
  }

  function conversationsForFolder(folderId: string): T[] {
    return conversationsInFolder(conversations.value, folderId)
  }

  return {
    showAllUncategorized,
    uncategorizedConversations,
    groupedUncategorized,
    hasMoreUncategorized,
    remainingUncategorizedCount,
    isFolderCollapsed,
    toggleFolderCollapsed,
    conversationsForFolder,
  }
}
