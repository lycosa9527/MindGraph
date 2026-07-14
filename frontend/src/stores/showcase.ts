/**
 * Showcase Pinia store — feed/list state + domain event helpers.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import {
  type ShowcasePost,
  type ShowcasePostList,
  getShowcasePosts,
} from '@/utils/apiClient'

export type ShowcaseFeedQuery = {
  caseType?: string
  expertRecommended?: boolean
  subject?: string
  grade?: string
  diagramType?: string
  publishSource?: string
  sort?: string
  search?: string
  status?: string
  mine?: boolean
  favorited?: boolean
  page?: number
  pageSize?: number
}

export const useShowcaseStore = defineStore('showcase', () => {
  const posts = ref<ShowcasePost[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastQuery = ref<ShowcaseFeedQuery | null>(null)

  const hasPosts = computed(() => posts.value.length > 0)

  function emitFeedInvalidate(reason?: string) {
    eventBus.emit('showcase:feed_invalidate', { reason })
  }

  function emitPostUpdated(postId: string) {
    eventBus.emit('showcase:post_updated', { postId })
  }

  function emitAdminUpdated() {
    eventBus.emit('admin:showcase_updated', {})
  }

  async function fetchPosts(query: ShowcaseFeedQuery = {}): Promise<ShowcasePostList> {
    loading.value = true
    error.value = null
    lastQuery.value = { ...query }
    try {
      const result = await getShowcasePosts({
        caseType: query.caseType,
        expertRecommended: query.expertRecommended,
        subject: query.subject,
        grade: query.grade,
        diagramType: query.diagramType,
        publishSource: query.publishSource,
        sort: query.sort,
        search: query.search,
        status: query.status,
        mine: query.mine,
        favorited: query.favorited,
        page: query.page ?? 1,
        pageSize: query.pageSize ?? pageSize.value,
      })
      posts.value = result.posts
      total.value = result.total
      page.value = result.page
      pageSize.value = result.page_size
      return result
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load showcase'
      error.value = message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function refresh(): Promise<ShowcasePostList | null> {
    if (!lastQuery.value) return null
    return fetchPosts(lastQuery.value)
  }

  function patchPost(postId: string, patch: Partial<ShowcasePost>) {
    const idx = posts.value.findIndex((p) => p.id === postId)
    if (idx < 0) return
    posts.value[idx] = { ...posts.value[idx], ...patch }
  }

  function removePost(postId: string) {
    posts.value = posts.value.filter((p) => p.id !== postId)
    if (total.value > 0) total.value -= 1
  }

  function reset() {
    posts.value = []
    total.value = 0
    page.value = 1
    error.value = null
    lastQuery.value = null
  }

  return {
    posts,
    total,
    page,
    pageSize,
    loading,
    error,
    lastQuery,
    hasPosts,
    fetchPosts,
    refresh,
    patchPost,
    removePost,
    reset,
    emitFeedInvalidate,
    emitPostUpdated,
    emitAdminUpdated,
  }
})
