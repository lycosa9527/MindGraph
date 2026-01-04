<script setup lang="ts">
/**
 * DiagramTypeGrid - Grid of diagram type cards with hover effect
 * Migrated from prototype MindMateChatPage diagram grid
 */
import { useRouter } from 'vue-router'

import { useUIStore } from '@/stores'

const uiStore = useUIStore()
const router = useRouter()

// Main diagram types (8 Thinking Maps)
const mainDiagramTypes = [
  { name: '圆圈图', icon: '⭕', desc: '联想 脑暴' },
  { name: '气泡图', icon: '🗨️', desc: '描述特性' },
  { name: '双气泡图', icon: '🔄', desc: '比较与对比' },
  { name: '树形图', icon: '🌳', desc: '分类与归纳' },
  { name: '括号图', icon: '📊', desc: '整体与部分' },
  { name: '流程图', icon: '➡️', desc: '顺序与步骤' },
  { name: '复流程图', icon: '🔄', desc: '因果分析' },
  { name: '桥型图', icon: '🌉', desc: '类比推理' },
]

// Extra diagram types
const extraDiagramTypes = [
  { name: '思维导图', icon: '🧠', desc: '概念梳理' },
  { name: '概念图', icon: '🌐', desc: '概念关系' },
]

function handleSelectType(name: string) {
  uiStore.setSelectedChartType(name)
}

function handleNewCanvas(name: string) {
  router.push({
    path: '/canvas',
    query: { type: name },
  })
}
</script>

<template>
  <div class="diagram-type-grid">
    <!-- Section title -->
    <div class="text-left font-bold text-gray-500 mb-4">在画布中创建</div>

    <!-- Main grid -->
    <div class="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-8 gap-3">
      <div
        v-for="item in mainDiagramTypes"
        :key="item.name"
        class="diagram-card relative flex flex-col items-center p-3 border border-gray-200 rounded-lg hover:border-blue-400 hover:shadow-md transition-all cursor-pointer overflow-hidden group"
        @click="handleSelectType(item.name)"
      >
        <!-- Normal content -->
        <div class="text-2xl mb-2 group-hover:opacity-30 transition-opacity duration-200">
          {{ item.icon }}
        </div>
        <div
          class="text-sm font-medium text-gray-800 mb-1 group-hover:opacity-30 transition-opacity duration-200"
        >
          {{ item.name }}
        </div>
        <div
          class="text-xs text-gray-500 text-center group-hover:opacity-30 transition-opacity duration-200"
        >
          {{ item.desc }}
        </div>

        <!-- Hover overlay -->
        <div
          class="absolute inset-0 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 p-2"
        >
          <button
            class="w-full py-2 px-4 bg-blue-600 text-white rounded-lg shadow-sm hover:bg-blue-700 transition-colors text-sm font-medium"
            @click.stop="handleNewCanvas(item.name)"
          >
            新建
          </button>
        </div>
      </div>
    </div>

    <!-- Extra types grid -->
    <div class="mt-4 grid grid-cols-2 sm:grid-cols-4 md:grid-cols-8 gap-3">
      <div
        v-for="item in extraDiagramTypes"
        :key="item.name"
        class="diagram-card relative flex flex-col items-center p-3 border border-gray-200 rounded-lg hover:border-blue-400 hover:shadow-md transition-all cursor-pointer overflow-hidden group"
        @click="handleSelectType(item.name)"
      >
        <!-- Normal content -->
        <div class="text-2xl mb-2 group-hover:opacity-30 transition-opacity duration-200">
          {{ item.icon }}
        </div>
        <div
          class="text-sm font-medium text-gray-800 mb-1 group-hover:opacity-30 transition-opacity duration-200"
        >
          {{ item.name }}
        </div>
        <div
          class="text-xs text-gray-500 text-center group-hover:opacity-30 transition-opacity duration-200"
        >
          {{ item.desc }}
        </div>

        <!-- Hover overlay -->
        <div
          class="absolute inset-0 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 p-2"
        >
          <button
            class="w-full py-2 px-4 bg-blue-600 text-white rounded-lg shadow-sm hover:bg-blue-700 transition-colors text-sm font-medium"
            @click.stop="handleNewCanvas(item.name)"
          >
            新建
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
