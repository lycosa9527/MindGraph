<script setup lang="ts">
/**
 * CommunityPage - Community sharing page (BBS-like)
 * Features: User shared diagrams, likes, filters, Me tab, Edit/Delete
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useInfiniteScroll } from '@vueuse/core'

import { ElButton, ElEmpty, ElMessageBox, ElSkeleton } from 'element-plus'
import { Heart, MessageCircle, Pencil, Search, Share2, Trash2 } from 'lucide-vue-next'

import { CommunityPostDetailModal } from '@/components/community'
import { ExportToCommunityModal } from '@/components/canvas'
import { useLanguage, useNotifications } from '@/composables'
import {
  deleteCommunityPost,
  getCommunityPost,
  getCommunityPosts,
  toggleCommunityPostLike,
  type CommunityPost,
} from '@/utils/apiClient'
import { useAuthStore } from '@/stores'

const notify = useNotifications()
const authStore = useAuthStore()
const { isZh } = useLanguage()

// Filter options - 我的 is shown as header button when authenticated
const typeOptions = ['全部', 'MindMate', 'MindGraph'] as const

const categoryOptions = [
  '全部',
  '学习笔记',
  '教学设计',
  '读书感悟',
  '工作总结',
  '创意灵感',
  '知识整理',
] as const

const sortOptions = ['最新发布', '最多点赞', '最多评论'] as const

const sortToApi = (s: string) =>
  s === '最多点赞' ? 'likes' : s === '最多评论' ? 'comments' : 'newest'

// Active filters
const activeType = ref<string>('全部')
const activeCategory = ref<string>('全部')
const activeSort = ref<string>('最新发布')
const searchQuery = ref('')

// Data
const posts = ref<CommunityPost[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const isLoading = ref(false)
const loadError = ref<string | null>(null)

// Edit modal
const showEditModal = ref(false)
const editingPost = ref<(CommunityPost & { spec?: unknown }) | null>(null)

// Detail modal (post click)
const showDetailModal = ref(false)
const selectedPostId = ref<string | null>(null)
const selectedPostPreview = ref<CommunityPost | null>(null)

function openPostDetail(p: CommunityPost) {
  selectedPostId.value = p.id
  selectedPostPreview.value = p
  showDetailModal.value = true
}

function handleDetailLikeToggled(updated: CommunityPost) {
  const idx = posts.value.findIndex((x) => x.id === updated.id)
  if (idx >= 0) {
    posts.value[idx] = { ...posts.value[idx], ...updated }
  }
}

const isLoadingMore = ref(false)
const scrollContainerRef = ref<HTMLElement | null>(null)

async function fetchPosts(append = false) {
  if (!authStore.isAuthenticated && activeType.value === '我的') return

  if (append) {
    isLoadingMore.value = true
  } else {
    isLoading.value = true
  }
  loadError.value = null
  try {
    const typeFilter =
      activeType.value === '全部' || activeType.value === '我的'
        ? undefined
        : activeType.value
    const categoryFilter =
      activeCategory.value === '全部' ? undefined : activeCategory.value

    const res = await getCommunityPosts({
      page: page.value,
      pageSize,
      mine: activeType.value === '我的',
      type: typeFilter,
      category: categoryFilter,
      sort: sortToApi(activeSort.value),
    })
    if (append) {
      posts.value = [...posts.value, ...res.posts]
    } else {
      posts.value = res.posts
    }
    total.value = res.total
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : 'Failed to load posts'
    if (!append) posts.value = []
  } finally {
    isLoading.value = false
    isLoadingMore.value = false
  }
}

function loadMore() {
  if (isLoading.value || isLoadingMore.value) return
  const totalPages = Math.ceil(total.value / pageSize)
  if (page.value >= totalPages) return
  if (searchQuery.value.trim()) return
  page.value += 1
  fetchPosts(true)
}

const canLoadMore = computed(
  () =>
    !isLoading.value &&
    !isLoadingMore.value &&
    page.value < Math.ceil(total.value / pageSize) &&
    !searchQuery.value.trim()
)

useInfiniteScroll(
  scrollContainerRef,
  () => loadMore(),
  { distance: 200, direction: 'bottom', canLoadMore: () => canLoadMore.value }
)

onMounted(() => {
  fetchPosts()
})

watch(
  [activeType, activeCategory, activeSort],
  () => {
    page.value = 1
    fetchPosts()
  }
)

// Client-side search filter (API doesn't support search)
const filteredPosts = computed(() => {
  if (!searchQuery.value.trim()) return posts.value
  const q = searchQuery.value.toLowerCase()
  return posts.value.filter(
    (p) =>
      p.title.toLowerCase().includes(q) ||
      (p.description?.toLowerCase() ?? '').includes(q)
  )
})

function setType(type: string) {
  activeType.value = type
}

function setCategory(cat: string) {
  activeCategory.value = cat
}

function setSort(sort: string) {
  activeSort.value = sort
}

function formatNumber(num: number): string {
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k'
  return num.toString()
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 60) return isZh.value ? `${diffMins}分钟前` : `${diffMins}m ago`
  if (diffHours < 24) return isZh.value ? `${diffHours}小时前` : `${diffHours}h ago`
  if (diffDays < 7) return isZh.value ? `${diffDays}天前` : `${diffDays}d ago`
  return isZh.value ? d.toLocaleDateString('zh-CN') : d.toLocaleDateString()
}

async function toggleLike(post: CommunityPost) {
  if (!authStore.isAuthenticated) return
  try {
    const res = await toggleCommunityPostLike(post.id)
    post.is_liked = res.is_liked
    post.likes_count = res.likes_count
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed to toggle like')
  }
}

function canEditPost(post: CommunityPost): boolean {
  return Boolean(post.can_edit)
}

async function openEdit(post: CommunityPost) {
  try {
    const full = await getCommunityPost(post.id)
    editingPost.value = full
    showEditModal.value = true
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed to load post')
  }
}

function closeEditModal() {
  showEditModal.value = false
  editingPost.value = null
}

async function handleEditSuccess(updated: CommunityPost) {
  const idx = posts.value.findIndex((p) => p.id === updated.id)
  if (idx >= 0) {
    posts.value[idx] = { ...posts.value[idx], ...updated }
  }
  closeEditModal()
}

async function confirmDelete(post: CommunityPost) {
  try {
    await ElMessageBox.confirm(
      isZh.value ? '确定删除此分享？' : 'Delete this post?',
      isZh.value ? '确认删除' : 'Confirm Delete',
      {
        confirmButtonText: isZh.value ? '删除' : 'Delete',
        cancelButtonText: isZh.value ? '取消' : 'Cancel',
        type: 'warning',
      }
    )
  } catch {
    return
  }

  try {
    await deleteCommunityPost(post.id)
    notify.success(isZh.value ? '已删除' : 'Deleted')
    posts.value = posts.value.filter((p) => p.id !== post.id)
    total.value = Math.max(0, total.value - 1)
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed to delete')
  }
}

function getPlaceholderColor(id: string): string {
  const colors = [
    'from-rose-400 to-pink-500',
    'from-violet-400 to-purple-500',
    'from-blue-400 to-indigo-500',
    'from-teal-400 to-emerald-500',
    'from-amber-400 to-orange-500',
    'from-cyan-400 to-blue-500',
    'from-fuchsia-400 to-pink-500',
    'from-lime-400 to-green-500',
  ]
  const index = parseInt(id) % colors.length
  return colors[index]
}
</script>

<template>
  <div class="community-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <!-- Header -->
    <div class="community-header px-6 py-5 bg-white border-b border-stone-200">
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-semibold text-stone-900">社区分享</h1>
        <div class="flex items-center gap-3">
          <div class="relative">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
            <input
              v-model="searchQuery"
              type="text"
              :placeholder="isZh ? '搜索作品...' : 'Search posts...'"
              class="pl-10 pr-4 py-2 w-64 rounded-lg border border-stone-200 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 transition-all"
            />
          </div>
          <ElButton
            v-if="authStore.isAuthenticated"
            size="small"
            :type="activeType === '我的' ? 'primary' : 'default'"
            class="my-posts-btn"
            @click="setType('我的')"
          >
            {{ isZh ? '我的' : 'My posts' }}
          </ElButton>
        </div>
      </div>

      <!-- Filter rows -->
      <div class="space-y-3">
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-stone-600 w-12 flex-shrink-0">类型</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="type in typeOptions"
              :key="type"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                activeType === type
                  ? 'bg-stone-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200',
              ]"
              @click="setType(type)"
            >
              {{ type }}
            </button>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-stone-600 w-12 flex-shrink-0">分类</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="cat in categoryOptions"
              :key="cat"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                activeCategory === cat
                  ? 'bg-stone-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200',
              ]"
              @click="setCategory(cat)"
            >
              {{ cat }}
            </button>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-stone-600 w-12 flex-shrink-0">排序</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="sort in sortOptions"
              :key="sort"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                activeSort === sort
                  ? 'bg-stone-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200',
              ]"
              @click="setSort(sort)"
            >
              {{ sort }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Posts grid -->
    <div
      ref="scrollContainerRef"
      class="community-grid flex-1 overflow-y-auto p-6"
    >
      <div
        v-if="loadError"
        class="flex flex-col items-center justify-center py-8 text-rose-600"
      >
        <p>{{ loadError }}</p>
      </div>

      <ElSkeleton
        v-else-if="isLoading && posts.length === 0"
        :rows="8"
        animated
        class="p-4"
      />

      <div
        v-else-if="filteredPosts.length > 0"
        class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5"
      >
        <div
          v-for="post in filteredPosts"
          :key="post.id"
          class="post-card bg-white rounded-xl shadow-sm border border-stone-100 overflow-hidden group cursor-pointer hover:shadow-md transition-all"
          @click="openPostDetail(post)"
        >
          <!-- Thumbnail -->
          <div
            :class="[
              'aspect-[16/10] relative',
              post.thumbnail_url ? '' : 'bg-gradient-to-br',
              post.thumbnail_url ? '' : getPlaceholderColor(post.id),
            ]"
          >
            <img
              v-if="post.thumbnail_url"
              :src="post.thumbnail_url"
              :alt="post.title"
              loading="lazy"
              class="w-full h-full object-cover"
            />
            <div
              v-else
              class="absolute inset-0 flex items-center justify-center opacity-20"
            >
              <svg
                class="w-16 h-16 text-white"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
              >
                <circle cx="12" cy="12" r="3" />
                <path d="M12 9V3" />
                <path d="M12 15v6" />
                <path d="M9 12H3" />
                <path d="M15 12h6" />
              </svg>
            </div>
            <div
              class="absolute top-2 left-2 bg-white/90 text-xs font-medium px-2 py-1 rounded-full text-stone-700"
            >
              MindGraph
            </div>
            <div
              v-if="post.category"
              class="absolute top-2 right-2 bg-black/50 text-white text-xs px-2 py-1 rounded-full"
            >
              {{ post.category }}
            </div>
          </div>

          <!-- Content -->
          <div class="p-4">
            <div class="flex items-center gap-2 mb-3">
              <div
                class="w-7 h-7 rounded-full bg-stone-100 flex items-center justify-center text-sm"
              >
                {{ post.author.avatar ?? '👤' }}
              </div>
              <span class="text-sm text-stone-600">{{ post.author.name ?? 'Anonymous' }}</span>
              <span class="text-xs text-stone-400 ml-auto">{{ formatDate(post.created_at) }}</span>
            </div>

            <h3 class="text-sm font-semibold text-stone-800 mb-2 line-clamp-1 group-hover:text-rose-600 transition-colors">
              {{ post.title }}
            </h3>
            <p class="text-xs text-stone-500 line-clamp-2 mb-3">
              {{ post.description || '' }}
            </p>

            <!-- Actions -->
            <div class="flex items-center gap-4 pt-3 border-t border-stone-100">
              <button
                :class="[
                  'flex items-center gap-1 text-xs transition-colors',
                  post.is_liked ? 'text-rose-500' : 'text-stone-400 hover:text-rose-500',
                ]"
                @click.stop="toggleLike(post)"
              >
                <Heart
                  class="w-4 h-4"
                  :fill="post.is_liked ? 'currentColor' : 'none'"
                />
                {{ formatNumber(post.likes_count) }}
              </button>
              <button
                class="flex items-center gap-1 text-xs text-stone-400 hover:text-blue-500 transition-colors"
              >
                <MessageCircle class="w-4 h-4" />
                {{ formatNumber(post.comments_count) }}
              </button>
              <div class="ml-auto flex items-center gap-2">
                <button
                  v-if="canEditPost(post)"
                  class="flex items-center gap-1 text-xs text-stone-400 hover:text-blue-500 transition-colors"
                  @click.stop="openEdit(post)"
                >
                  <Pencil class="w-4 h-4" />
                  {{ isZh ? '编辑' : 'Edit' }}
                </button>
                <button
                  v-if="canEditPost(post)"
                  class="flex items-center gap-1 text-xs text-stone-400 hover:text-rose-500 transition-colors"
                  @click.stop="confirmDelete(post)"
                >
                  <Trash2 class="w-4 h-4" />
                  {{ isZh ? '删除' : 'Delete' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="isLoadingMore"
          class="col-span-full flex justify-center py-6 text-stone-400 text-sm"
        >
          {{ isZh ? '加载更多...' : 'Loading more...' }}
        </div>
      </div>

      <ElEmpty
        v-else
        :description="
          isZh ? '没有找到匹配的作品，尝试调整筛选条件或搜索关键词' : 'No posts found. Try adjusting filters or search'
        "
        :image-size="120"
        class="flex-1 flex items-center justify-center min-h-[300px]"
      />
    </div>

    <!-- Edit modal -->
    <ExportToCommunityModal
      v-model:visible="showEditModal"
      mode="edit"
      :diagram-type="editingPost?.diagram_type ?? 'mind_map'"
      :initial-post="editingPost"
      @success="handleEditSuccess"
    />

    <!-- Post detail modal -->
    <CommunityPostDetailModal
      v-model:visible="showDetailModal"
      :post-id="selectedPostId"
      :post-preview="selectedPostPreview"
      @like-toggled="handleDetailLikeToggled"
    />
  </div>
</template>

<style scoped>
.community-page {
  min-height: 0;
}

.my-posts-btn {
  font-weight: 500;
  border-radius: 9999px;
}

.my-posts-btn.el-button--default {
  --el-button-bg-color: #f5f5f4;
  --el-button-border-color: #e7e5e4;
  --el-button-hover-bg-color: #e7e5e4;
  --el-button-hover-border-color: #d6d3d1;
  --el-button-text-color: #57534e;
}

.my-posts-btn.el-button--primary {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
}

.post-card {
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.post-card:hover {
  transform: translateY(-2px);
}

.community-grid::-webkit-scrollbar {
  width: 6px;
}

.community-grid::-webkit-scrollbar-track {
  background: transparent;
}

.community-grid::-webkit-scrollbar-thumb {
  background: #d6d3d1;
  border-radius: 3px;
}

.community-grid::-webkit-scrollbar-thumb:hover {
  background: #a8a29e;
}

.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
