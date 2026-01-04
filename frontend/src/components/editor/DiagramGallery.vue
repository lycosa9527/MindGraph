<script setup lang="ts">
/**
 * Diagram Gallery - Grid of diagram type cards with prompt input
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useLanguage } from '@/composables'
import { useAuthStore, useUIStore } from '@/stores'
import type { DiagramType } from '@/types'

import DiagramCard from './DiagramCard.vue'
import PromptInput from './PromptInput.vue'

defineProps<{
  isGenerating?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', type: DiagramType): void
  (e: 'submitPrompt', prompt: string): void
}>()

const router = useRouter()
const authStore = useAuthStore()
const uiStore = useUIStore()
const { isZh } = useLanguage()

// Diagram types with metadata
const diagramTypes = computed(() => [
  {
    type: 'bubble_map' as DiagramType,
    icon: 'bubble',
    nameEn: 'Bubble Map',
    nameZh: '气泡图',
    descEn: 'Describe qualities and attributes',
    descZh: '描述事物的特征和属性',
  },
  {
    type: 'circle_map' as DiagramType,
    icon: 'circle',
    nameEn: 'Circle Map',
    nameZh: '圆圈图',
    descEn: 'Define in context',
    descZh: '在上下文中定义概念',
  },
  {
    type: 'double_bubble_map' as DiagramType,
    icon: 'double-bubble',
    nameEn: 'Double Bubble Map',
    nameZh: '双气泡图',
    descEn: 'Compare and contrast',
    descZh: '比较和对比两个事物',
  },
  {
    type: 'tree_map' as DiagramType,
    icon: 'tree',
    nameEn: 'Tree Map',
    nameZh: '树形图',
    descEn: 'Classify and group',
    descZh: '分类和分组',
  },
  {
    type: 'brace_map' as DiagramType,
    icon: 'brace',
    nameEn: 'Brace Map',
    nameZh: '括号图',
    descEn: 'Part-whole relationships',
    descZh: '整体与部分的关系',
  },
  {
    type: 'flow_map' as DiagramType,
    icon: 'flow',
    nameEn: 'Flow Map',
    nameZh: '流程图',
    descEn: 'Sequence and order',
    descZh: '顺序和流程',
  },
  {
    type: 'multi_flow_map' as DiagramType,
    icon: 'multi-flow',
    nameEn: 'Multi-Flow Map',
    nameZh: '多重流程图',
    descEn: 'Cause and effect',
    descZh: '因果关系',
  },
  {
    type: 'bridge_map' as DiagramType,
    icon: 'bridge',
    nameEn: 'Bridge Map',
    nameZh: '桥型图',
    descEn: 'Seeing analogies',
    descZh: '类比关系',
  },
  {
    type: 'concept_map' as DiagramType,
    icon: 'concept',
    nameEn: 'Concept Map',
    nameZh: '概念图',
    descEn: 'Connect ideas',
    descZh: '连接想法和概念',
  },
  {
    type: 'mindmap' as DiagramType,
    icon: 'mindmap',
    nameEn: 'Mind Map',
    nameZh: '思维导图',
    descEn: 'Organize thoughts',
    descZh: '组织思维',
  },
])

function handleSelect(type: DiagramType) {
  emit('select', type)
}

function handlePromptSubmit(prompt: string) {
  emit('submitPrompt', prompt)
}

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}

function goToAdmin() {
  router.push('/admin')
}
</script>

<template>
  <div
    class="diagram-gallery h-full overflow-y-auto bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800"
  >
    <!-- Top Controls -->
    <div class="absolute top-4 right-4 flex items-center gap-2 z-10">
      <el-button
        circle
        @click="uiStore.toggleLanguage"
      >
        {{ uiStore.language === 'zh' ? 'EN' : '中' }}
      </el-button>
      <el-button
        v-if="authStore.isAdmin"
        circle
        @click="goToAdmin"
      >
        <el-icon><Setting /></el-icon>
      </el-button>
      <el-button
        circle
        @click="handleLogout"
      >
        <el-icon><SwitchButton /></el-icon>
      </el-button>
    </div>

    <div class="max-w-6xl mx-auto px-6 py-12">
      <!-- Header -->
      <header class="text-center mb-12">
        <h1 class="text-4xl font-bold text-gray-800 dark:text-white mb-3">
          MindGraph Professional
        </h1>
        <p class="text-lg text-gray-500 dark:text-gray-400">
          {{ isZh ? '选择图表类型开始创建' : 'Choose a diagram type to start creating' }}
        </p>
      </header>

      <!-- Prompt Input Section -->
      <div class="mb-12">
        <PromptInput
          :is-loading="isGenerating"
          @submit="handlePromptSubmit"
        />
      </div>

      <!-- Diagram Type Divider -->
      <div class="flex items-center gap-4 mb-8">
        <div class="flex-1 h-px bg-gray-200 dark:bg-gray-700" />
        <span class="text-sm text-gray-400 dark:text-gray-500">
          {{ isZh ? '或选择图表类型' : 'or select a diagram type' }}
        </span>
        <div class="flex-1 h-px bg-gray-200 dark:bg-gray-700" />
      </div>

      <!-- Diagram Cards Grid -->
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <DiagramCard
          v-for="diagram in diagramTypes"
          :key="diagram.type"
          :type="diagram.type"
          :name="isZh ? diagram.nameZh : diagram.nameEn"
          :description="isZh ? diagram.descZh : diagram.descEn"
          :icon="diagram.icon"
          @click="handleSelect(diagram.type)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.diagram-gallery {
  position: relative;
}
</style>
