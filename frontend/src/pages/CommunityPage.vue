<script setup lang="ts">
/**
 * CommunityPage - Community sharing page (BBS-like)
 * Features: User shared diagrams, likes, comments, filters
 */
import { computed, ref } from 'vue'

import { Heart, MessageCircle, Search, Share2, Users } from 'lucide-vue-next'

// Filter options
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

// Active filters
const activeType = ref<string>('全部')
const activeCategory = ref<string>('全部')
const activeSort = ref<string>('最新发布')
const searchQuery = ref('')

// Shared post type
interface SharedPost {
  id: string
  title: string
  description: string
  thumbnail: string
  type: 'MindMate' | 'MindGraph'
  category: string
  author: {
    name: string
    avatar: string
  }
  likes: number
  comments: number
  shares: number
  createdAt: string
  isLiked: boolean
}

// Mock shared posts data
const mockPosts: SharedPost[] = [
  {
    id: '1',
    title: '高中物理力学知识框架',
    description:
      '整理了高中物理力学部分的核心知识点，包括牛顿三定律、动量守恒等，希望对大家有帮助！',
    thumbnail: '',
    type: 'MindGraph',
    category: '学习笔记',
    author: { name: '学霸小明', avatar: '🧑‍🎓' },
    likes: 234,
    comments: 45,
    shares: 12,
    createdAt: '2小时前',
    isLiked: false,
  },
  {
    id: '2',
    title: '《三体》读书笔记思维导图',
    description: '三体三部曲的完整梳理，包含主要人物关系、科技概念和故事脉络。',
    thumbnail: '',
    type: 'MindGraph',
    category: '读书感悟',
    author: { name: '科幻迷', avatar: '🚀' },
    likes: 567,
    comments: 89,
    shares: 45,
    createdAt: '5小时前',
    isLiked: true,
  },
  {
    id: '3',
    title: '小学三年级语文教学设计',
    description: '基于思维图示的语文课堂教学设计，培养学生的思维能力和阅读理解能力。',
    thumbnail: '',
    type: 'MindGraph',
    category: '教学设计',
    author: { name: '王老师', avatar: '👩‍🏫' },
    likes: 189,
    comments: 34,
    shares: 28,
    createdAt: '1天前',
    isLiked: false,
  },
  {
    id: '4',
    title: '产品经理年度工作总结',
    description: '用思维导图总结了2024年的产品工作，包括项目复盘、能力成长和未来规划。',
    thumbnail: '',
    type: 'MindGraph',
    category: '工作总结',
    author: { name: 'PM小李', avatar: '💼' },
    likes: 345,
    comments: 56,
    shares: 23,
    createdAt: '2天前',
    isLiked: false,
  },
  {
    id: '5',
    title: 'AI辅助学习英语的方法',
    description: '分享我用MindMate学习英语的心得，包括词汇记忆、语法理解和口语练习。',
    thumbnail: '',
    type: 'MindMate',
    category: '学习笔记',
    author: { name: '英语爱好者', avatar: '🌍' },
    likes: 456,
    comments: 78,
    shares: 34,
    createdAt: '3天前',
    isLiked: true,
  },
  {
    id: '6',
    title: '创业公司商业模式画布',
    description: '用概念图梳理创业想法，从价值主张到客户细分，全方位思考商业模式。',
    thumbnail: '',
    type: 'MindGraph',
    category: '创意灵感',
    author: { name: '创业者阿杰', avatar: '💡' },
    likes: 234,
    comments: 45,
    shares: 19,
    createdAt: '3天前',
    isLiked: false,
  },
  {
    id: '7',
    title: '初中化学元素周期表速记',
    description: '用气泡图帮助记忆元素周期表，附带各族元素的性质特点。',
    thumbnail: '',
    type: 'MindGraph',
    category: '知识整理',
    author: { name: '化学课代表', avatar: '🧪' },
    likes: 678,
    comments: 123,
    shares: 56,
    createdAt: '4天前',
    isLiked: false,
  },
  {
    id: '8',
    title: '班级读书分享会策划',
    description: '主题班会活动策划思维导图，包括活动流程、分组安排和评价标准。',
    thumbnail: '',
    type: 'MindGraph',
    category: '教学设计',
    author: { name: '班主任张老师', avatar: '📚' },
    likes: 123,
    comments: 23,
    shares: 15,
    createdAt: '5天前',
    isLiked: false,
  },
  {
    id: '9',
    title: '用AI整理会议纪要',
    description: '分享如何用MindMate快速整理会议内容，生成结构化的会议纪要。',
    thumbnail: '',
    type: 'MindMate',
    category: '工作总结',
    author: { name: '效率达人', avatar: '⚡' },
    likes: 345,
    comments: 67,
    shares: 28,
    createdAt: '1周前',
    isLiked: true,
  },
  {
    id: '10',
    title: '《活着》人物关系图',
    description: '余华《活着》中福贵一家的命运轨迹和人物关系梳理。',
    thumbnail: '',
    type: 'MindGraph',
    category: '读书感悟',
    author: { name: '文学青年', avatar: '📖' },
    likes: 456,
    comments: 89,
    shares: 41,
    createdAt: '1周前',
    isLiked: false,
  },
]

// Filtered and sorted posts
const filteredPosts = computed(() => {
  let posts = mockPosts.filter((post) => {
    const matchesType = activeType.value === '全部' || post.type === activeType.value
    const matchesCategory =
      activeCategory.value === '全部' || post.category === activeCategory.value
    const matchesSearch =
      !searchQuery.value ||
      post.title.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      post.description.toLowerCase().includes(searchQuery.value.toLowerCase())
    return matchesType && matchesCategory && matchesSearch
  })

  // Sort
  if (activeSort.value === '最多点赞') {
    posts = [...posts].sort((a, b) => b.likes - a.likes)
  } else if (activeSort.value === '最多评论') {
    posts = [...posts].sort((a, b) => b.comments - a.comments)
  }

  return posts
})

function setType(type: string) {
  activeType.value = type
}

function setCategory(category: string) {
  activeCategory.value = category
}

function setSort(sort: string) {
  activeSort.value = sort
}

function formatNumber(num: number): string {
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toString()
}

function toggleLike(post: SharedPost) {
  post.isLiked = !post.isLiked
  post.likes += post.isLiked ? 1 : -1
}

// Generate placeholder colors based on post id
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
        <!-- Search -->
        <div class="relative">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索作品..."
            class="pl-10 pr-4 py-2 w-64 rounded-lg border border-stone-200 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 transition-all"
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
                  ? 'bg-stone-900 text-white'
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
                  ? 'bg-stone-900 text-white'
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
    <div class="community-grid flex-1 overflow-y-auto p-6">
      <div
        v-if="filteredPosts.length > 0"
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
              <svg
                class="w-16 h-16 text-white"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
              >
                <circle
                  cx="12"
                  cy="12"
                  r="3"
                />
                <path d="M12 9V3" />
                <path d="M12 15v6" />
                <path d="M9 12H3" />
                <path d="M15 12h6" />
              </svg>
            </div>
            <!-- Type badge -->
            <div
              class="absolute top-2 left-2 bg-white/90 text-xs font-medium px-2 py-1 rounded-full text-stone-700"
            >
              {{ post.type }}
            </div>
            <!-- Category badge -->
            <div
              class="absolute top-2 right-2 bg-black/50 text-white text-xs px-2 py-1 rounded-full"
            >
              {{ post.category }}
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
              <span class="text-xs text-stone-400 ml-auto">{{ post.createdAt }}</span>
            </div>

            <!-- Title & Description -->
            <h3
              class="text-sm font-semibold text-stone-800 mb-2 line-clamp-1 group-hover:text-rose-600 transition-colors"
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
                  post.isLiked ? 'text-rose-500' : 'text-stone-400 hover:text-rose-500',
                ]"
                @click.stop="toggleLike(post)"
              >
                <Heart
                  class="w-4 h-4"
                  :fill="post.isLiked ? 'currentColor' : 'none'"
                />
                {{ formatNumber(post.likes) }}
              </button>
              <button
                class="flex items-center gap-1 text-xs text-stone-400 hover:text-blue-500 transition-colors"
              >
                <MessageCircle class="w-4 h-4" />
                {{ formatNumber(post.comments) }}
              </button>
              <button
                class="flex items-center gap-1 text-xs text-stone-400 hover:text-green-500 transition-colors ml-auto"
              >
                <Share2 class="w-4 h-4" />
                {{ formatNumber(post.shares) }}
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
        <p class="text-lg font-medium mb-1">没有找到匹配的作品</p>
        <p class="text-sm">尝试调整筛选条件或搜索关键词</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.community-page {
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
