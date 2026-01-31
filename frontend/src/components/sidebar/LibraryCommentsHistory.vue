<script setup lang="ts">
/**
 * LibraryCommentsHistory - Grouped list of recent library bookmarks
 * Design: Clean minimalist grouped by time periods
 * Shows max 10 items initially with "Show more" option
 */
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { ElScrollbar } from 'element-plus'

import { Bookmark, Trash2, FileText } from 'lucide-vue-next'

import { useLanguage } from '@/composables'
import { type LibraryBookmark } from '@/utils/apiClient'
import { useNotifications } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { useLibraryStore } from '@/stores/library'

defineProps<{
  isBlurred?: boolean
}>()

const { isZh } = useLanguage()
const router = useRouter()
const notify = useNotifications()
const authStore = useAuthStore()
const libraryStore = useLibraryStore()

// Show all or just 10
const showAll = ref(false)
const INITIAL_LIMIT = 10

// Use bookmarks from store
const bookmarks = computed(() => libraryStore.bookmarks)
const loading = computed(() => libraryStore.bookmarksLoading)

// Fetch recent bookmarks
async function fetchRecentBookmarks() {
  // Only fetch if user is authenticated
  if (!authStore.isAuthenticated) {
    return
  }
  await libraryStore.fetchRecentBookmarks()
}

onMounted(() => {
  fetchRecentBookmarks()
})

// Group bookmarks by time period
interface GroupedBookmarks {
  today: LibraryBookmark[]
  yesterday: LibraryBookmark[]
  week: LibraryBookmark[]
  month: LibraryBookmark[]
}

const groupedBookmarks = computed((): GroupedBookmarks => {
  const groups: GroupedBookmarks = {
    today: [],
    yesterday: [],
    week: [],
    month: [],
  }

  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterdayStart = todayStart - 24 * 60 * 60 * 1000
  const weekStart = todayStart - 7 * 24 * 60 * 60 * 1000

  // Limit to 10 unless showAll
  const items = showAll.value ? bookmarks.value : bookmarks.value.slice(0, INITIAL_LIMIT)

  items.forEach((bookmark) => {
    const bookmarkTime = new Date(bookmark.created_at).getTime()

    if (bookmarkTime >= todayStart) {
      groups.today.push(bookmark)
    } else if (bookmarkTime >= yesterdayStart) {
      groups.yesterday.push(bookmark)
    } else if (bookmarkTime >= weekStart) {
      groups.week.push(bookmark)
    } else {
      groups.month.push(bookmark)
    }
  })

  return groups
})

// Check if there are more bookmarks to show
const hasMore = computed(() => bookmarks.value.length > INITIAL_LIMIT && !showAll.value)
const remainingCount = computed(() => bookmarks.value.length - INITIAL_LIMIT)

// Group labels
const groupLabels = computed(() => ({
  today: isZh.value ? '今天' : 'Today',
  yesterday: isZh.value ? '昨天' : 'Yesterday',
  week: isZh.value ? '上周' : 'Past Week',
  month: isZh.value ? '上月' : 'Past Month',
}))

// Handle bookmark click - navigate to document and page
// If bookmark doesn't exist or doesn't belong to user, navigate to 404 page
async function handleBookmarkClick(bookmark: LibraryBookmark): Promise<void> {
  try {
    // Verify bookmark still exists and belongs to user before navigating
    // This will throw 404 if bookmark was deleted or doesn't belong to user
    const { getBookmark } = await import('@/utils/apiClient')
    await getBookmark(bookmark.document_id, bookmark.page_number)
    
    // Bookmark exists - navigate to it
    router.push({
      name: 'LibraryViewer',
      params: { id: bookmark.document_id.toString() },
      query: { page: bookmark.page_number.toString() },
    })
  } catch (error) {
    // Bookmark doesn't exist or doesn't belong to user - navigate to 404 page
    console.error('[LibraryCommentsHistory] Bookmark not found:', error)
    // Refresh bookmark list to remove stale bookmark
    await libraryStore.fetchRecentBookmarks()
    // Navigate to 404 page
    router.push({ name: 'NotFound' })
  }
}

// Handle delete bookmark
async function handleDeleteBookmark(bookmark: LibraryBookmark, event: Event): Promise<void> {
  event.stopPropagation()
  try {
    await libraryStore.deleteBookmark(bookmark.id)
    // Store automatically updates bookmarks list
    notify.success(isZh.value ? '书签已删除' : 'Bookmark deleted')
  } catch (error) {
    console.error('[LibraryCommentsHistory] Failed to delete bookmark:', error)
    notify.error(isZh.value ? '删除书签失败' : 'Failed to delete bookmark')
  }
}

// Toggle show all
function toggleShowAll(): void {
  showAll.value = !showAll.value
}
</script>

<template>
  <div class="library-comments-history flex flex-col border-t border-stone-200 relative overflow-hidden">
    <!-- Header -->
    <div class="px-4 py-3">
      <div class="text-xs font-medium text-stone-400 uppercase tracking-wider">
        {{ isZh ? '最近书签' : 'Recent Bookmarks' }}
      </div>
    </div>

    <!-- Scrollable bookmark list -->
    <ElScrollbar class="flex-1 px-4 pb-4">
      <div :class="isBlurred ? 'blur-sm pointer-events-none select-none' : ''">
        <!-- Loading State -->
        <div
          v-if="loading"
          class="text-center py-8"
        >
          <div class="text-xs text-stone-400">
            {{ isZh ? '加载中...' : 'Loading...' }}
          </div>
        </div>

        <!-- Empty State -->
        <div
          v-else-if="bookmarks.length === 0"
          class="text-center py-8"
        >
          <Bookmark class="w-8 h-8 mx-auto mb-2 text-stone-300" />
          <p class="text-xs text-stone-400">
            {{ isZh ? '暂无书签' : 'No bookmarks yet' }}
          </p>
        </div>

        <!-- Grouped Bookmark List -->
        <template v-else>
          <!-- Today -->
          <div
            v-if="groupedBookmarks.today.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.today }}</div>
            <div
              v-for="bookmark in groupedBookmarks.today"
              :key="bookmark.id"
              class="comment-item"
            >
              <div
                class="comment-content"
                @click="handleBookmarkClick(bookmark)"
              >
                <div class="comment-text">
                  {{ bookmark.document?.title || (isZh ? '未知文档' : 'Unknown Document') }}
                </div>
                <div class="comment-meta">
                  <FileText class="w-3 h-3" />
                  <span class="text-xs text-stone-400">
                    {{ isZh ? `第 ${bookmark.page_number} 页` : `Page ${bookmark.page_number}` }}
                  </span>
                </div>
              </div>
              <button
                class="delete-btn"
                @click.stop="handleDeleteBookmark(bookmark, $event)"
                :title="isZh ? '删除书签' : 'Delete bookmark'"
              >
                <Trash2 class="w-4 h-4" />
              </button>
            </div>
          </div>

          <!-- Yesterday -->
          <div
            v-if="groupedBookmarks.yesterday.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.yesterday }}</div>
            <div
              v-for="bookmark in groupedBookmarks.yesterday"
              :key="bookmark.id"
              class="comment-item"
            >
              <div
                class="comment-content"
                @click="handleBookmarkClick(bookmark)"
              >
                <div class="comment-text">
                  {{ bookmark.document?.title || (isZh ? '未知文档' : 'Unknown Document') }}
                </div>
                <div class="comment-meta">
                  <FileText class="w-3 h-3" />
                  <span class="text-xs text-stone-400">
                    {{ isZh ? `第 ${bookmark.page_number} 页` : `Page ${bookmark.page_number}` }}
                  </span>
                </div>
              </div>
              <button
                class="delete-btn"
                @click.stop="handleDeleteBookmark(bookmark, $event)"
                :title="isZh ? '删除书签' : 'Delete bookmark'"
              >
                <Trash2 class="w-4 h-4" />
              </button>
            </div>
          </div>

          <!-- Past Week -->
          <div
            v-if="groupedBookmarks.week.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.week }}</div>
            <div
              v-for="bookmark in groupedBookmarks.week"
              :key="bookmark.id"
              class="comment-item"
            >
              <div
                class="comment-content"
                @click="handleBookmarkClick(bookmark)"
              >
                <div class="comment-text">
                  {{ bookmark.document?.title || (isZh ? '未知文档' : 'Unknown Document') }}
                </div>
                <div class="comment-meta">
                  <FileText class="w-3 h-3" />
                  <span class="text-xs text-stone-400">
                    {{ isZh ? `第 ${bookmark.page_number} 页` : `Page ${bookmark.page_number}` }}
                  </span>
                </div>
              </div>
              <button
                class="delete-btn"
                @click.stop="handleDeleteBookmark(bookmark, $event)"
                :title="isZh ? '删除书签' : 'Delete bookmark'"
              >
                <Trash2 class="w-4 h-4" />
              </button>
            </div>
          </div>

          <!-- Past Month -->
          <div
            v-if="groupedBookmarks.month.length > 0"
            class="group-section"
          >
            <div class="group-label">{{ groupLabels.month }}</div>
            <div
              v-for="bookmark in groupedBookmarks.month"
              :key="bookmark.id"
              class="comment-item"
            >
              <div
                class="comment-content"
                @click="handleBookmarkClick(bookmark)"
              >
                <div class="comment-text">
                  {{ bookmark.document?.title || (isZh ? '未知文档' : 'Unknown Document') }}
                </div>
                <div class="comment-meta">
                  <FileText class="w-3 h-3" />
                  <span class="text-xs text-stone-400">
                    {{ isZh ? `第 ${bookmark.page_number} 页` : `Page ${bookmark.page_number}` }}
                  </span>
                </div>
              </div>
              <button
                class="delete-btn"
                @click.stop="handleDeleteBookmark(bookmark, $event)"
                :title="isZh ? '删除书签' : 'Delete bookmark'"
              >
                <Trash2 class="w-4 h-4" />
              </button>
            </div>
          </div>

          <!-- Show More button -->
          <button
            v-if="hasMore"
            class="show-more-btn"
            @click="toggleShowAll"
          >
            {{ isZh ? `显示更多 (${remainingCount})` : `Show more (${remainingCount})` }}
          </button>

          <!-- Show Less button -->
          <button
            v-if="showAll && bookmarks.length > INITIAL_LIMIT"
            class="show-more-btn"
            @click="toggleShowAll"
          >
            {{ isZh ? '收起' : 'Show less' }}
          </button>
        </template>
      </div>
    </ElScrollbar>

    <!-- Login overlay when blurred -->
    <div
      v-if="isBlurred"
      class="absolute inset-0 flex items-center justify-center bg-stone-50/60 backdrop-blur-[2px]"
    >
      <div class="text-center px-4">
        <div
          class="w-10 h-10 rounded-full bg-stone-100 flex items-center justify-center mx-auto mb-2"
        >
          <Bookmark class="w-5 h-5 text-stone-400" />
        </div>
        <p class="text-xs text-stone-500">
          {{ isZh ? '登录后查看最近书签' : 'Login to view recent bookmarks' }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.library-comments-history {
  min-height: 120px;
}

.group-section {
  margin-bottom: 12px;
}

.group-section:last-child {
  margin-bottom: 0;
}

.group-label {
  font-size: 11px;
  font-weight: 500;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  margin-bottom: 4px;
  padding-left: 2px;
}

.comment-item {
  display: flex;
  align-items: flex-start;
  width: 100%;
  padding: 8px;
  border-radius: 6px;
  color: #57534e;
  font-size: 13px;
  text-align: left;
  transition: background-color 0.15s ease;
  cursor: pointer;
  border: none;
  background: transparent;
}

.comment-item:hover {
  background-color: #f5f5f4;
}

.comment-content {
  flex: 1;
  min-width: 0;
}

.comment-text {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.4;
  margin-bottom: 4px;
}

.comment-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #78716c;
}

.delete-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  margin-left: 8px;
  opacity: 0;
  color: #dc2626;
  transition: all 0.15s ease;
  background: transparent;
  border: none;
  cursor: pointer;
  border-radius: 4px;
}

.comment-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background-color: #fee2e2;
  color: #991b1b;
}

.delete-btn:active {
  background-color: #fecaca;
}

.show-more-btn {
  display: block;
  width: 100%;
  padding: 8px;
  margin-top: 8px;
  font-size: 12px;
  color: #78716c;
  text-align: center;
  background: transparent;
  border: 1px dashed #d6d3d1;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.show-more-btn:hover {
  background-color: #fafaf9;
  border-color: #a8a29e;
  color: #57534e;
}
</style>
