/**
 * ZhiHui conversation history — list, detail, and store-owned job poller.
 * Emits zhihui:* events on the app event bus for studio / sidebar consumers.
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import { apiDelete, apiGet } from '@/utils/apiClient'

export type ZhihuiConversationStatus =
  | 'queued'
  | 'planning'
  | 'generating'
  | 'complete'
  | 'partial'
  | 'failed'
  | 'cancelled'

export type ZhihuiGenerationItem = {
  id: string
  prompt: string
  enhanced_prompt?: string | null
  language: string
  image_url: string
  created_at?: string | null
  size?: string | null
  slide_index?: number | null
  slide_title?: string | null
  focus_node_ids?: string[] | null
  conversation_id?: string | null
}

export type ZhihuiConversationItem = {
  id: string
  mode: 'image' | 'diagram' | string
  title: string
  status: ZhihuiConversationStatus | string
  progress?: Record<string, unknown> | null
  error_message?: string | null
  diagram_id?: string | null
  diagram_title?: string | null
  language?: string
  slide_count?: number
  cover_image_url?: string | null
  created_at?: string | null
  updated_at?: string | null
  style_seed?: string | null
  planner_model?: string | null
  image_model?: string | null
  lesson_plan_json?: Record<string, unknown> | null
  generations?: ZhihuiGenerationItem[]
}

/** @deprecated Use ZhihuiConversationItem — kept for gradual call-site updates. */
export type ZhihuiHistoryItem = ZhihuiConversationItem & {
  prompt?: string
  image_url?: string
}

const TITLE_MAX = 40
const POLL_MS = 2500

export function zhihuiConversationTitle(item: ZhihuiConversationItem): string {
  const raw = (item.title || item.diagram_title || '').replace(/\s+/g, ' ').trim()
  if (!raw) return ''
  if (raw.length <= TITLE_MAX) return raw
  return `${raw.slice(0, TITLE_MAX)}…`
}

/** @deprecated Prefer zhihuiConversationTitle */
export function zhihuiItemTitle(item: ZhihuiHistoryItem): string {
  if (item.title) return zhihuiConversationTitle(item)
  const raw = (item.prompt || '').replace(/\s+/g, ' ').trim()
  if (!raw) return ''
  if (raw.length <= TITLE_MAX) return raw
  return `${raw.slice(0, TITLE_MAX)}…`
}

export function isZhihuiJobActive(status: string | undefined | null): boolean {
  return status === 'queued' || status === 'planning' || status === 'generating'
}

export const useZhihuiHistoryStore = defineStore('zhihuiHistory', () => {
  const items = ref<ZhihuiConversationItem[]>([])
  const isLoading = ref(false)
  const loadError = ref(false)
  const currentId = ref<string | null>(null)
  const currentDetail = ref<ZhihuiConversationItem | null>(null)
  const pollingId = ref<string | null>(null)

  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let pollInFlight = false
  let pollEpoch = 0
  let loadEpoch = 0

  const currentItem = computed(
    () => items.value.find((row) => row.id === currentId.value) ?? currentDetail.value
  )

  const sortedItems = computed(() => {
    return [...items.value].sort((a, b) => {
      const ta = a.updated_at
        ? Date.parse(a.updated_at)
        : a.created_at
          ? Date.parse(a.created_at)
          : 0
      const tb = b.updated_at
        ? Date.parse(b.updated_at)
        : b.created_at
          ? Date.parse(b.created_at)
          : 0
      return tb - ta
    })
  })

  function mergeDetail(detail: ZhihuiConversationItem): void {
    currentDetail.value = detail
    const idx = items.value.findIndex((row) => row.id === detail.id)
    if (idx >= 0) {
      items.value[idx] = {
        ...items.value[idx],
        ...detail,
        generations: detail.generations,
      }
    } else {
      items.value = [detail, ...items.value]
    }
    const slideCount = detail.generations?.length ?? detail.slide_count ?? 0
    eventBus.emit('zhihui:conversation_updated', {
      conversationId: detail.id,
      status: String(detail.status),
      slideCount,
    })
  }

  function stopPolling(): void {
    pollEpoch += 1
    if (pollTimer !== null) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
    pollingId.value = null
    pollInFlight = false
  }

  function schedulePoll(conversationId: string, epoch: number): void {
    if (pollTimer !== null) {
      clearTimeout(pollTimer)
    }
    pollTimer = window.setTimeout(() => {
      void runPollTick(conversationId, epoch)
    }, POLL_MS)
  }

  async function runPollTick(conversationId: string, epoch: number): Promise<void> {
    if (epoch !== pollEpoch || pollingId.value !== conversationId) {
      return
    }
    if (typeof document !== 'undefined' && document.hidden) {
      schedulePoll(conversationId, epoch)
      return
    }
    if (pollInFlight) {
      schedulePoll(conversationId, epoch)
      return
    }
    pollInFlight = true
    try {
      const detail = await loadConversation(conversationId)
      if (epoch !== pollEpoch || pollingId.value !== conversationId) {
        return
      }
      if (!detail) {
        stopPolling()
        return
      }
      if (!isZhihuiJobActive(detail.status)) {
        stopPolling()
        eventBus.emit('zhihui:job_terminal', {
          conversationId: detail.id,
          status: String(detail.status),
        })
        void fetchHistory()
        return
      }
      schedulePoll(conversationId, epoch)
    } finally {
      pollInFlight = false
    }
  }

  function startPolling(conversationId: string): void {
    if (pollingId.value === conversationId && pollTimer !== null) {
      return
    }
    stopPolling()
    const epoch = pollEpoch
    pollingId.value = conversationId
    void runPollTick(conversationId, epoch)
  }

  async function fetchHistory(): Promise<void> {
    isLoading.value = true
    loadError.value = false
    try {
      const res = await apiGet('/api/zhihui/conversations?offset=0&limit=100')
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }
      const data = (await res.json()) as { items?: ZhihuiConversationItem[] }
      const next = data.items ?? []
      // Soft-merge: never drop an in-flight selection just because the list lagged.
      if (
        currentId.value &&
        currentDetail.value?.id === currentId.value &&
        !next.some((row) => row.id === currentId.value)
      ) {
        items.value = [currentDetail.value, ...next]
      } else {
        items.value = next
      }
    } catch {
      loadError.value = true
      items.value = []
    } finally {
      isLoading.value = false
    }
  }

  async function loadConversation(id: string): Promise<ZhihuiConversationItem | null> {
    const epoch = ++loadEpoch
    const res = await apiGet(`/api/zhihui/conversations/${id}`)
    if (epoch !== loadEpoch) {
      return currentDetail.value?.id === id ? currentDetail.value : null
    }
    if (!res.ok) {
      if (res.status === 404 && currentId.value === id) {
        currentId.value = null
        currentDetail.value = null
        if (pollingId.value === id) {
          stopPolling()
        }
      }
      return null
    }
    const detail = (await res.json()) as ZhihuiConversationItem
    if (epoch !== loadEpoch) {
      return detail
    }
    mergeDetail(detail)
    return detail
  }

  function selectItem(id: string | null): void {
    currentId.value = id
    if (!id) {
      currentDetail.value = null
      stopPolling()
      return
    }
  }

  async function deleteItem(id: string): Promise<boolean> {
    if (pollingId.value === id) {
      stopPolling()
    }
    const res = await apiDelete(`/api/zhihui/conversations/${id}`)
    if (!res.ok) {
      return false
    }
    items.value = items.value.filter((row) => row.id !== id)
    if (currentId.value === id) {
      currentId.value = null
      currentDetail.value = null
    }
    return true
  }

  function upsertConversation(item: ZhihuiConversationItem): void {
    const idx = items.value.findIndex((row) => row.id === item.id)
    if (idx >= 0) {
      items.value[idx] = { ...items.value[idx], ...item }
    } else {
      items.value = [item, ...items.value]
    }
  }

  return {
    items,
    sortedItems,
    isLoading,
    loadError,
    currentId,
    currentItem,
    currentDetail,
    pollingId,
    fetchHistory,
    loadConversation,
    selectItem,
    deleteItem,
    upsertConversation,
    startPolling,
    stopPolling,
  }
})
