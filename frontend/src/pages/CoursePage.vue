<script setup lang="ts">
/**
 * CoursePage - Thinking course library with diagram-specific filters
 * Features: Type filters, Diagram filters, Course thumbnails
 */
import { computed, ref } from 'vue'

import { BookOpen, Play, Search } from 'lucide-vue-next'

// Filter options
const typeOptions = ['全部', 'MindMate', 'MindGraph'] as const
const sceneOptions = ['全部', '教学通用', '主题班会', '总结汇报'] as const
const diagramOptions = [
  '全部',
  '思维教学',
  '八大思维图示',
  '圆圈图',
  '气泡图',
  '双气泡图',
  '树形图',
  '括号图',
  '流程图',
  '复流程图',
  '桥形图',
  '思维导图',
  '概念图',
] as const

// Active filters
const activeType = ref<string>('全部')
const activeScene = ref<string>('全部')
const activeDiagram = ref<string>('全部')
const searchQuery = ref('')

// Course resource type
interface CourseResource {
  id: string
  title: string
  thumbnail: string
  type: 'MindMate' | 'MindGraph'
  scene: string
  diagram: string
  duration: string
  lessons: number
  views: number
}

// Mock course data (will be replaced with API later)
const mockCourses: CourseResource[] = [
  {
    id: '1',
    title: '圆圈图入门：联想思维训练',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    diagram: '圆圈图',
    duration: '15分钟',
    lessons: 5,
    views: 2345,
  },
  {
    id: '2',
    title: '气泡图：描述事物特征',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    diagram: '气泡图',
    duration: '20分钟',
    lessons: 6,
    views: 1890,
  },
  {
    id: '3',
    title: '双气泡图：对比分析技巧',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    diagram: '双气泡图',
    duration: '25分钟',
    lessons: 7,
    views: 1567,
  },
  {
    id: '4',
    title: '树形图：分类整理方法',
    thumbnail: '',
    type: 'MindGraph',
    scene: '总结汇报',
    diagram: '树形图',
    duration: '18分钟',
    lessons: 5,
    views: 3456,
  },
  {
    id: '5',
    title: '括号图：整体与部分关系',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    diagram: '括号图',
    duration: '22分钟',
    lessons: 6,
    views: 987,
  },
  {
    id: '6',
    title: '流程图：顺序思维培养',
    thumbnail: '',
    type: 'MindGraph',
    scene: '总结汇报',
    diagram: '流程图',
    duration: '30分钟',
    lessons: 8,
    views: 4567,
  },
  {
    id: '7',
    title: '复流程图：因果分析进阶',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    diagram: '复流程图',
    duration: '35分钟',
    lessons: 9,
    views: 2134,
  },
  {
    id: '8',
    title: '桥形图：类比推理训练',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    diagram: '桥形图',
    duration: '28分钟',
    lessons: 7,
    views: 1789,
  },
  {
    id: '9',
    title: '八大思维图示综合应用',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    diagram: '八大思维图示',
    duration: '45分钟',
    lessons: 12,
    views: 5678,
  },
  {
    id: '10',
    title: '思维导图：知识整合技巧',
    thumbnail: '',
    type: 'MindGraph',
    scene: '总结汇报',
    diagram: '思维导图',
    duration: '40分钟',
    lessons: 10,
    views: 6789,
  },
  {
    id: '11',
    title: '概念图：深度理解与建构',
    thumbnail: '',
    type: 'MindGraph',
    scene: '教学通用',
    diagram: '概念图',
    duration: '50分钟',
    lessons: 14,
    views: 3456,
  },
  {
    id: '12',
    title: '思维教学：课堂实践指南',
    thumbnail: '',
    type: 'MindMate',
    scene: '教学通用',
    diagram: '思维教学',
    duration: '60分钟',
    lessons: 15,
    views: 4321,
  },
  {
    id: '13',
    title: 'AI辅助思维训练入门',
    thumbnail: '',
    type: 'MindMate',
    scene: '教学通用',
    diagram: '思维教学',
    duration: '35分钟',
    lessons: 8,
    views: 2345,
  },
  {
    id: '14',
    title: '主题班会设计：思维图示应用',
    thumbnail: '',
    type: 'MindGraph',
    scene: '主题班会',
    diagram: '八大思维图示',
    duration: '40分钟',
    lessons: 10,
    views: 1876,
  },
]

// Filtered courses
const filteredCourses = computed(() => {
  return mockCourses.filter((course) => {
    const matchesType = activeType.value === '全部' || course.type === activeType.value
    const matchesScene = activeScene.value === '全部' || course.scene === activeScene.value
    const matchesDiagram = activeDiagram.value === '全部' || course.diagram === activeDiagram.value
    const matchesSearch =
      !searchQuery.value || course.title.toLowerCase().includes(searchQuery.value.toLowerCase())
    return matchesType && matchesScene && matchesDiagram && matchesSearch
  })
})

// Shuffle courses for randomized display
const displayCourses = computed(() => {
  const courses = [...filteredCourses.value]
  for (let i = courses.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[courses[i], courses[j]] = [courses[j], courses[i]]
  }
  return courses
})

function setType(type: string) {
  activeType.value = type
}

function setScene(scene: string) {
  activeScene.value = scene
}

function setDiagram(diagram: string) {
  activeDiagram.value = diagram
}

function formatNumber(num: number): string {
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toString()
}

// Generate placeholder colors based on course id
function getPlaceholderColor(id: string): string {
  const colors = [
    'from-indigo-400 to-purple-500',
    'from-teal-400 to-cyan-500',
    'from-rose-400 to-pink-500',
    'from-amber-400 to-orange-500',
    'from-emerald-400 to-green-500',
    'from-blue-400 to-indigo-500',
    'from-fuchsia-400 to-purple-500',
    'from-sky-400 to-blue-500',
  ]
  const index = parseInt(id) % colors.length
  return colors[index]
}
</script>

<template>
  <div class="course-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <!-- Header -->
    <div class="course-header px-6 py-5 bg-white border-b border-stone-200">
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-semibold text-stone-900">思维课程</h1>
        <!-- Search -->
        <div class="relative">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索课程..."
            class="pl-10 pr-4 py-2 w-64 rounded-lg border border-stone-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all"
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

        <!-- Diagram filter -->
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-stone-600 w-12 flex-shrink-0">图示</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="diagram in diagramOptions"
              :key="diagram"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium transition-all',
                activeDiagram === diagram
                  ? 'bg-stone-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200',
              ]"
              @click="setDiagram(diagram)"
            >
              {{ diagram }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Course grid -->
    <div class="course-grid flex-1 overflow-y-auto p-6">
      <div
        v-if="displayCourses.length > 0"
        class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-5"
      >
        <div
          v-for="course in displayCourses"
          :key="course.id"
          class="course-card group cursor-pointer"
        >
          <!-- Thumbnail -->
          <div
            :class="[
              'aspect-video rounded-xl overflow-hidden mb-3 relative',
              'bg-gradient-to-br',
              getPlaceholderColor(course.id),
            ]"
          >
            <!-- Placeholder pattern -->
            <div class="absolute inset-0 flex items-center justify-center opacity-30">
              <svg
                class="w-12 h-12 text-white"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
              >
                <polygon
                  points="5 3 19 12 5 21 5 3"
                  fill="currentColor"
                />
              </svg>
            </div>
            <!-- Play button overlay -->
            <div
              class="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center"
            >
              <div
                class="w-12 h-12 rounded-full bg-white/90 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all transform scale-90 group-hover:scale-100"
              >
                <Play
                  class="w-5 h-5 text-stone-800 ml-0.5"
                  fill="currentColor"
                />
              </div>
            </div>
            <!-- Duration badge -->
            <div
              class="absolute bottom-2 right-2 bg-black/70 text-white text-xs px-2 py-0.5 rounded"
            >
              {{ course.duration }}
            </div>
          </div>

          <!-- Info -->
          <div class="px-1">
            <h3
              class="text-sm font-medium text-stone-800 line-clamp-2 mb-2 group-hover:text-indigo-600 transition-colors"
            >
              {{ course.title }}
            </h3>
            <div class="flex items-center gap-3 text-xs text-stone-400">
              <span>{{ course.lessons }} 节课</span>
              <span>{{ formatNumber(course.views) }} 观看</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-else
        class="flex flex-col items-center justify-center h-full text-stone-400"
      >
        <BookOpen class="w-16 h-16 mb-4 opacity-30" />
        <p class="text-lg font-medium mb-1">没有找到匹配的课程</p>
        <p class="text-sm">尝试调整筛选条件或搜索关键词</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.course-page {
  min-height: 0;
}

.course-card {
  transition: transform 0.2s ease;
}

.course-card:hover {
  transform: translateY(-2px);
}

/* Custom scrollbar */
.course-grid::-webkit-scrollbar {
  width: 6px;
}

.course-grid::-webkit-scrollbar-track {
  background: transparent;
}

.course-grid::-webkit-scrollbar-thumb {
  background: #d6d3d1;
  border-radius: 3px;
}

.course-grid::-webkit-scrollbar-thumb:hover {
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
