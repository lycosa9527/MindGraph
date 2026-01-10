<script setup lang="ts">
/**
 * SchoolZonePage - Organization-scoped sharing page
 * Features: Shared diagrams/courses within same organization
 * Only visible to users who belong to an organization
 */
import { computed, onMounted, ref } from 'vue'

import { Files, Heart, MessageCircle, Network, Search, Share2, Users, Video } from 'lucide-vue-next'

import { useAuthStore } from '@/stores'

const authStore = useAuthStore()

// Organization info
const organizationName = computed(() => authStore.user?.schoolName || '我的学校')

// Filter options
const typeOptions = ['全部', 'MindMate课程', 'MindGraph图示'] as const
const categoryOptions = [
  '全部',
  '教学设计',
  '学科资源',
  '班级管理',
  '教研活动',
  '学生作品',
  '校本课程',
] as const
const sortOptions = ['最新发布', '最多点赞', '最多评论'] as const

// Active filters
const activeType = ref<string>('全部')
const activeCategory = ref<string>('全部')
const activeSort = ref<string>('最新发布')
const searchQuery = ref('')
const isLoading = ref(false)

// Shared post type
interface SharedPost {
  id: string
  title: string
  description: string
  thumbnail: string
  content_type: string
  category: string
  author: {
    id: string
    name: string
    avatar: string
  }
  likes_count: number
  comments_count: number
  shares_count: number
  created_at: string
  is_liked: boolean
}

// Posts from API
const posts = ref<SharedPost[]>([])

// Map content_type to display type
function getDisplayType(contentType: string): string {
  return contentType === 'mindmate' ? 'MindMate课程' : 'MindGraph图示'
}

// Map display type to content_type for API
function getApiType(displayType: string): string | null {
  if (displayType === 'MindMate课程') return 'mindmate'
  if (displayType === 'MindGraph图示') return 'mindgraph'
  return null
}

// Map display sort to API sort
function getApiSort(displaySort: string): string {
  if (displaySort === '最多点赞') return 'likes'
  if (displaySort === '最多评论') return 'comments'
  return 'newest'
}

// Filtered posts (search is done client-side for responsiveness)
const filteredPosts = computed(() => {
  if (!searchQuery.value) return posts.value

  const query = searchQuery.value.toLowerCase()
  return posts.value.filter(
    (post) =>
      post.title.toLowerCase().includes(query) ||
      (post.description && post.description.toLowerCase().includes(query))
  )
})

function setType(type: string) {
  activeType.value = type
  loadPosts()
}

function setCategory(category: string) {
  activeCategory.value = category
  loadPosts()
}

function setSort(sort: string) {
  activeSort.value = sort
  loadPosts()
}

function formatNumber(num: number): string {
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toString()
}

// Format relative time
function formatRelativeTime(isoString: string): string {
  if (!isoString) return ''
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins}分钟前`
  if (diffHours < 24) return `${diffHours}小时前`
  if (diffDays < 7) return `${diffDays}天前`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}周前`
  return `${Math.floor(diffDays / 30)}个月前`
}

async function toggleLike(post: SharedPost) {
  try {
    // Use credentials (token in httpOnly cookie)
    const response = await fetch(`/api/school-zone/posts/${post.id}/like`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
    })

    if (response.status === 401) {
      authStore.handleTokenExpired('您的登录已过期，请重新登录')
      return
    }

    if (response.ok) {
      const data = await response.json()
      post.is_liked = data.is_liked
      post.likes_count = data.likes_count
    }
  } catch (error) {
    console.error('Failed to toggle like:', error)
  }
}

// Generate placeholder colors based on post id (works with UUID)
function getPlaceholderColor(id: string): string {
  const colors = [
    'from-blue-400 to-indigo-500',
    'from-emerald-400 to-teal-500',
    'from-amber-400 to-orange-500',
    'from-violet-400 to-purple-500',
    'from-cyan-400 to-blue-500',
    'from-rose-400 to-pink-500',
  ]
  // Simple hash from string: sum of char codes
  let hash = 0
  for (let i = 0; i < id.length; i++) {
    hash += id.charCodeAt(i)
  }
  const index = hash % colors.length
  return colors[index]
}

// Get icon for post type
function getTypeIcon(contentType: string) {
  if (contentType === 'mindmate') return Video
  return Network
}

// Load posts from API
async function loadPosts() {
  isLoading.value = true
  try {
    const params = new URLSearchParams()

    // Add content type filter
    const apiType = getApiType(activeType.value)
    if (apiType) {
      params.append('content_type', apiType)
    }

    // Add category filter
    if (activeCategory.value !== '全部') {
      params.append('category', activeCategory.value)
    }

    // Add sort
    params.append('sort', getApiSort(activeSort.value))

    // Use credentials (token in httpOnly cookie)
    const response = await fetch(`/api/school-zone/posts?${params.toString()}`, {
      credentials: 'same-origin',
    })

    if (response.status === 401) {
      authStore.handleTokenExpired('您的登录已过期，请重新登录后查看校园动态')
      posts.value = []
      return
    }

    if (response.ok) {
      const data = await response.json()
      posts.value = data.posts || []
    } else {
      console.error('Failed to load posts:', response.status)
      posts.value = []
    }
  } catch (error) {
    console.error('Failed to load posts:', error)
    posts.value = []
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadPosts()
})
</script>

<template>
  <div class="school-zone-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <!-- Header -->
    <div class="school-zone-header px-6 py-5 bg-white border-b border-stone-200">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
          <div
            class="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white"
          >
            <Files class="w-5 h-5" />
          </div>
          <div>
            <h1 class="text-xl font-semibold text-stone-900">学校专区</h1>
            <p class="text-sm text-stone-500">{{ organizationName }} 专属资源共享空间</p>
          </div>
        </div>
        <!-- Search -->
        <div class="relative">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索资源..."
            class="pl-10 pr-4 py-2 w-64 rounded-lg border border-stone-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
          />
        </div>
      </div>

      <!-- Filter rows -->
      <div class="space-y-3">
        <!-- Type filter -->
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-stone-600 w-12 flex-shrink-0">类型</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="type in typeOptions"
              :key="type"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                activeType === type
                  ? 'bg-blue-600 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200',
              ]"
              @click="setType(type)"
            >
              {{ type }}
            </button>
          </div>
        </div>

        <!-- Category filter -->
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-stone-600 w-12 flex-shrink-0">分类</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="category in categoryOptions"
              :key="category"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                activeCategory === category
                  ? 'bg-blue-600 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200',
              ]"
              @click="setCategory(category)"
            >
              {{ category }}
            </button>
          </div>
        </div>

        <!-- Sort filter -->
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-stone-600 w-12 flex-shrink-0">排序</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="sort in sortOptions"
              :key="sort"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                activeSort === sort
                  ? 'bg-blue-600 text-white'
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
    <div class="school-zone-grid flex-1 overflow-y-auto p-6">
      <!-- Loading state -->
      <div
        v-if="isLoading"
        class="flex items-center justify-center h-full"
      >
        <div class="text-stone-400">加载中...</div>
      </div>

      <!-- Posts -->
      <div
        v-else-if="filteredPosts.length > 0"
        class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5"
      >
        <div
          v-for="post in filteredPosts"
          :key="post.id"
          class="post-card bg-white rounded-xl shadow-sm border border-stone-100 overflow-hidden group cursor-pointer hover:shadow-md transition-all"
        >
          <!-- Thumbnail -->
          <div
            :class="['aspect-[16/10] relative', 'bg-gradient-to-br', getPlaceholderColor(post.id)]"
          >
            <!-- Placeholder pattern -->
            <div class="absolute inset-0 flex items-center justify-center opacity-20">
              <component
                :is="getTypeIcon(post.content_type)"
                class="w-16 h-16 text-white"
              />
            </div>
            <!-- Type badge -->
            <div
              class="absolute top-2 left-2 bg-white/90 text-xs font-medium px-2 py-1 rounded-full text-stone-700 flex items-center gap-1"
            >
              <component
                :is="getTypeIcon(post.content_type)"
                class="w-3 h-3"
              />
              {{ getDisplayType(post.content_type) }}
            </div>
            <!-- Category badge -->
            <div
              class="absolute top-2 right-2 bg-black/50 text-white text-xs px-2 py-1 rounded-full"
            >
              {{ post.category || '未分类' }}
            </div>
          </div>

          <!-- Content -->
          <div class="p-4">
            <!-- Author -->
            <div class="flex items-center gap-2 mb-3">
              <div
                class="w-7 h-7 rounded-full bg-stone-100 flex items-center justify-center text-sm"
              >
                {{ post.author.avatar }}
              </div>
              <span class="text-sm text-stone-600">{{ post.author.name }}</span>
              <span class="text-xs text-stone-400 ml-auto">{{
                formatRelativeTime(post.created_at)
              }}</span>
            </div>

            <!-- Title & Description -->
            <h3
              class="text-sm font-semibold text-stone-800 mb-2 line-clamp-1 group-hover:text-blue-600 transition-colors"
            >
              {{ post.title }}
            </h3>
            <p class="text-xs text-stone-500 line-clamp-2 mb-3">
              {{ post.description }}
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
              <button
                class="flex items-center gap-1 text-xs text-stone-400 hover:text-green-500 transition-colors ml-auto"
              >
                <Share2 class="w-4 h-4" />
                {{ formatNumber(post.shares_count) }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-else
        class="flex flex-col items-center justify-center h-full text-stone-400"
      >
        <Users class="w-16 h-16 mb-4 opacity-30" />
        <p class="text-lg font-medium mb-1">暂无共享资源</p>
        <p class="text-sm">成为第一个分享资源的老师吧</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.school-zone-page {
  min-height: 0;
}

.post-card {
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.post-card:hover {
  transform: translateY(-2px);
}

/* Custom scrollbar */
.school-zone-grid::-webkit-scrollbar {
  width: 6px;
}

.school-zone-grid::-webkit-scrollbar-track {
  background: transparent;
}

.school-zone-grid::-webkit-scrollbar-thumb {
  background: #d6d3d1;
  border-radius: 3px;
}

.school-zone-grid::-webkit-scrollbar-thumb:hover {
  background: #a8a29e;
}

/* Line clamp */
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
