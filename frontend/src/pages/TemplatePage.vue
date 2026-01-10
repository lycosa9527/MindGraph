<script setup lang="ts">
/**
 * TemplatePage - Template library with filters and thumbnail grid
 * Features: Scene filters, Subject filters, Template thumbnails
 */
import { computed, ref } from 'vue'

import { Folder, Search } from 'lucide-vue-next'

// Filter options
const typeOptions = ['全部', 'MindMate', 'MindGraph'] as const
const sceneOptions = ['全部', '教学通用', '主题班会', '总结汇报'] as const
const subjectOptions = [
  '全部',
  '语文',
  '数学',
  '英语',
  '物理',
  '化学',
  '生物',
  '历史',
  '地理',
  '政治',
  '音乐',
  '美术',
  '体育',
  '信息技术',
  '综合实践',
] as const

// Active filters
const activeType = ref<string>('全部')
const activeScene = ref<string>('全部')
const activeSubject = ref<string>('全部')
const searchQuery = ref('')

// Template resource type
interface TemplateResource {
  id: string
  title: string
  thumbnail: string
  type: 'MindMate' | 'MindGraph'
  scene: string
  subject: string
  views: number
  downloads: number
}

// Mock template data (will be replaced with API later)
const mockTemplates: TemplateResource[] = [
  {
    id: '1',
    title: '小学语文课文思维导图模板',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    subject: '语文',
    views: 1234,
    downloads: 567,
  },
  {
    id: '2',
    title: '初中数学公式整理思维导图',
    thumbnail: '',
    type: 'MindGraph',
    scene: '总结汇报',
    subject: '数学',
    views: 2345,
    downloads: 890,
  },
  {
    id: '3',
    title: '英语语法知识点总结',
    thumbnail: '',
    type: 'MindMate',
    scene: '教学通用',
    subject: '英语',
    views: 1567,
    downloads: 432,
  },
  {
    id: '4',
    title: '高中化学元素周期表思维导图',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    subject: '化学',
    views: 3456,
    downloads: 1234,
  },
  {
    id: '5',
    title: '班级文化建设主题班会',
    thumbnail: '',
    type: 'MindMate',
    scene: '主题班会',
    subject: '综合实践',
    views: 987,
    downloads: 321,
  },
  {
    id: '6',
    title: '物理力学知识框架',
    thumbnail: '',
    type: 'MindGraph',
    scene: '总结汇报',
    subject: '物理',
    views: 2134,
    downloads: 765,
  },
  {
    id: '7',
    title: '历史朝代年表思维导图',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    subject: '历史',
    views: 4567,
    downloads: 1890,
  },
  {
    id: '8',
    title: '地理气候类型总结',
    thumbnail: '',
    type: 'MindMate',
    scene: '总结汇报',
    subject: '地理',
    views: 1789,
    downloads: 654,
  },
  {
    id: '9',
    title: '生物细胞结构图解',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    subject: '生物',
    views: 2890,
    downloads: 987,
  },
  {
    id: '10',
    title: '政治考点梳理思维导图',
    thumbnail: '',
    type: 'MindMate',
    scene: '总结汇报',
    subject: '政治',
    views: 1234,
    downloads: 456,
  },
  {
    id: '11',
    title: '音乐乐理知识框架',
    thumbnail: '',
    type: 'MindMate',
    scene: '教学通用',
    subject: '音乐',
    views: 876,
    downloads: 234,
  },
  {
    id: '12',
    title: '美术色彩理论思维导图',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    subject: '美术',
    views: 1567,
    downloads: 543,
  },
]

// Filtered templates
const filteredTemplates = computed(() => {
  return mockTemplates.filter((template) => {
    const matchesType = activeType.value === '全部' || template.type === activeType.value
    const matchesScene = activeScene.value === '全部' || template.scene === activeScene.value
    const matchesSubject =
      activeSubject.value === '全部' || template.subject === activeSubject.value
    const matchesSearch =
      !searchQuery.value || template.title.toLowerCase().includes(searchQuery.value.toLowerCase())
    return matchesType && matchesScene && matchesSubject && matchesSearch
  })
})

// Shuffle templates for randomized display
const displayTemplates = computed(() => {
  const templates = [...filteredTemplates.value]
  // Fisher-Yates shuffle for randomization
  for (let i = templates.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[templates[i], templates[j]] = [templates[j], templates[i]]
  }
  return templates
})

function setType(type: string) {
  activeType.value = type
}

function setScene(scene: string) {
  activeScene.value = scene
}

function setSubject(subject: string) {
  activeSubject.value = subject
}

function formatNumber(num: number): string {
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toString()
}

// Generate placeholder colors based on template id
function getPlaceholderColor(id: string): string {
  const colors = [
    'from-amber-400 to-orange-500',
    'from-emerald-400 to-teal-500',
    'from-blue-400 to-indigo-500',
    'from-purple-400 to-pink-500',
    'from-rose-400 to-red-500',
    'from-cyan-400 to-blue-500',
    'from-lime-400 to-green-500',
    'from-fuchsia-400 to-purple-500',
  ]
  const index = parseInt(id) % colors.length
  return colors[index]
}
</script>

<template>
  <div class="template-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <!-- Header -->
    <div class="template-header px-6 py-5 bg-white border-b border-stone-200">
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-semibold text-stone-900">模板资源</h1>
        <!-- Search -->
        <div class="relative">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索模板..."
            class="pl-10 pr-4 py-2 w-64 rounded-lg border border-stone-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 transition-all"
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

        <!-- Scene filter -->
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-stone-600 w-12 flex-shrink-0">场景</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="scene in sceneOptions"
              :key="scene"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                activeScene === scene
                  ? 'bg-stone-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200',
              ]"
              @click="setScene(scene)"
            >
              {{ scene }}
            </button>
          </div>
        </div>

        <!-- Subject filter -->
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-stone-600 w-12 flex-shrink-0">科目</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="subject in subjectOptions"
              :key="subject"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                activeSubject === subject
                  ? 'bg-stone-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200',
              ]"
              @click="setSubject(subject)"
            >
              {{ subject }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Template grid -->
    <div class="template-grid flex-1 overflow-y-auto p-6">
      <div
        v-if="displayTemplates.length > 0"
        class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-5"
      >
        <div
          v-for="template in displayTemplates"
          :key="template.id"
          class="template-card group cursor-pointer"
        >
          <!-- Thumbnail -->
          <div
            :class="[
              'aspect-[4/3] rounded-xl overflow-hidden mb-3 relative',
              'bg-gradient-to-br',
              getPlaceholderColor(template.id),
            ]"
          >
            <!-- Placeholder pattern -->
            <div class="absolute inset-0 flex items-center justify-center opacity-30">
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
                <path d="M9.17 9.17L4.93 4.93" />
                <path d="M14.83 14.83l4.24 4.24" />
                <path d="M9.17 14.83L4.93 19.07" />
                <path d="M14.83 9.17l4.24-4.24" />
              </svg>
            </div>
            <!-- Hover overlay -->
            <div
              class="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center"
            >
              <span
                class="text-white text-sm font-medium opacity-0 group-hover:opacity-100 transition-opacity bg-black/40 px-3 py-1.5 rounded-full"
              >
                使用模板
              </span>
            </div>
          </div>

          <!-- Info -->
          <div class="px-1">
            <h3
              class="text-sm font-medium text-stone-800 line-clamp-2 mb-2 group-hover:text-amber-600 transition-colors"
            >
              {{ template.title }}
            </h3>
            <div class="flex items-center gap-3 text-xs text-stone-400">
              <span>{{ formatNumber(template.views) }} 浏览</span>
              <span>{{ formatNumber(template.downloads) }} 使用</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-else
        class="flex flex-col items-center justify-center h-full text-stone-400"
      >
        <Folder class="w-16 h-16 mb-4 opacity-30" />
        <p class="text-lg font-medium mb-1">没有找到匹配的模板</p>
        <p class="text-sm">尝试调整筛选条件或搜索关键词</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.template-page {
  min-height: 0;
}

.template-card {
  transition: transform 0.2s ease;
}

.template-card:hover {
  transform: translateY(-2px);
}

/* Custom scrollbar */
.template-grid::-webkit-scrollbar {
  width: 6px;
}

.template-grid::-webkit-scrollbar-track {
  background: transparent;
}

.template-grid::-webkit-scrollbar-thumb {
  background: #d6d3d1;
  border-radius: 3px;
}

.template-grid::-webkit-scrollbar-thumb:hover {
  background: #a8a29e;
}

/* Line clamp */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
