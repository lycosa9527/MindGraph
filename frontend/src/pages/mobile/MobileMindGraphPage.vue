<script setup lang="ts">
/**
 * MobileMindGraphPage — Diagram type selection for mobile.
 * Custom header: Home + History toggle | "MindGraph" | (spacer).
 * Shows text input + diagram type grid. Tapping a type navigates to mobile canvas.
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { ElDrawer } from 'element-plus'

import { ArrowRight, Home, Menu } from 'lucide-vue-next'

import DiagramPreviewSvg from '@/components/mindgraph/DiagramPreviewSvg.vue'
import DiagramHistory from '@/components/sidebar/DiagramHistory.vue'
import { useLanguage } from '@/composables'
import { useUIStore } from '@/stores'
import type { SavedDiagram } from '@/stores/savedDiagrams'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'

const router = useRouter()
const uiStore = useUIStore()
const savedDiagramsStore = useSavedDiagramsStore()
const { t } = useLanguage()

const showHistoryDrawer = ref(false)

function goHome() {
  router.push('/m')
}

function toggleHistory() {
  showHistoryDrawer.value = !showHistoryDrawer.value
}

function handleSelectDiagram(diagram: SavedDiagram) {
  savedDiagramsStore.setCurrentDiagram(diagram.id)
  showHistoryDrawer.value = false
  router.push({
    path: '/m/canvas',
    query: { diagramId: diagram.id },
  })
}

const TYPE_TO_ZH_NAME: Record<DiagramType, string> = {
  circle_map: '圆圈图',
  bubble_map: '气泡图',
  double_bubble_map: '双气泡图',
  tree_map: '树形图',
  brace_map: '括号图',
  flow_map: '流程图',
  multi_flow_map: '复流程图',
  bridge_map: '桥形图',
  mindmap: '思维导图',
  mind_map: '思维导图',
  concept_map: '概念图',
  diagram: '图表',
}

const diagramTypes: Array<{ titleKey: string; descKey: string; type: DiagramType }> = [
  {
    titleKey: 'landing.diagramGrid.circle_map.title',
    descKey: 'landing.diagramGrid.circle_map.desc',
    type: 'circle_map',
  },
  {
    titleKey: 'landing.diagramGrid.bubble_map.title',
    descKey: 'landing.diagramGrid.bubble_map.desc',
    type: 'bubble_map',
  },
  {
    titleKey: 'landing.diagramGrid.double_bubble_map.title',
    descKey: 'landing.diagramGrid.double_bubble_map.desc',
    type: 'double_bubble_map',
  },
  {
    titleKey: 'landing.diagramGrid.tree_map.title',
    descKey: 'landing.diagramGrid.tree_map.desc',
    type: 'tree_map',
  },
  {
    titleKey: 'landing.diagramGrid.brace_map.title',
    descKey: 'landing.diagramGrid.brace_map.desc',
    type: 'brace_map',
  },
  {
    titleKey: 'landing.diagramGrid.flow_map.title',
    descKey: 'landing.diagramGrid.flow_map.desc',
    type: 'flow_map',
  },
  {
    titleKey: 'landing.diagramGrid.multi_flow_map.title',
    descKey: 'landing.diagramGrid.multi_flow_map.desc',
    type: 'multi_flow_map',
  },
  {
    titleKey: 'landing.diagramGrid.bridge_map.title',
    descKey: 'landing.diagramGrid.bridge_map.desc',
    type: 'bridge_map',
  },
  {
    titleKey: 'landing.diagramGrid.mindmap.title',
    descKey: 'landing.diagramGrid.mindmap.desc',
    type: 'mindmap',
  },
  {
    titleKey: 'landing.diagramGrid.concept_map.title',
    descKey: 'landing.diagramGrid.concept_map.desc',
    type: 'concept_map',
  },
]

function handleSelectType(item: { type: DiagramType }) {
  const zhName = TYPE_TO_ZH_NAME[item.type]
  if (zhName) {
    uiStore.setSelectedChartType(zhName)
  }
  router.push({
    path: '/m/canvas',
    query: { type: item.type },
  })
}

function handleFreeInput() {
  const text = uiStore.freeInputValue?.trim()
  if (!text) return
  router.push({
    path: '/m/canvas',
    query: { prompt: text },
  })
}
</script>

<template>
  <div class="mobile-mindgraph flex flex-col flex-1 min-h-0">
    <!-- Custom header -->
    <header
      class="mobile-mg-header flex items-center h-12 px-3 bg-white border-b border-gray-200 shrink-0"
    >
      <button
        class="flex items-center justify-center w-8 h-8 rounded-lg active:bg-gray-100 transition-colors"
        @click="goHome"
      >
        <Home
          :size="18"
          class="text-gray-500"
        />
      </button>
      <button
        class="flex items-center justify-center w-8 h-8 rounded-lg active:bg-gray-100 transition-colors ml-0.5"
        @click="toggleHistory"
      >
        <Menu
          :size="18"
          class="text-gray-500"
        />
      </button>

      <h1 class="flex-1 text-center text-base font-semibold text-gray-800 truncate">MindGraph</h1>

      <div class="w-[72px] shrink-0" />
    </header>

    <!-- History Drawer -->
    <ElDrawer
      v-model="showHistoryDrawer"
      direction="ltr"
      :size="'80%'"
      :title="t('sidebar.diagramHistory.title', '图示历史')"
      class="diagram-history-drawer"
      :z-index="2000"
    >
      <DiagramHistory @select="handleSelectDiagram" />
    </ElDrawer>

    <!-- Page content -->
    <div class="flex-1 overflow-y-auto">
      <div class="px-4 pt-4 pb-8 max-w-md mx-auto">
        <!-- Free text input -->
        <div class="relative mb-5">
          <input
            v-model="uiStore.freeInputValue"
            type="text"
            class="w-full h-12 pl-4 pr-12 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all"
            :placeholder="
              t('mindgraphLanding.inputPlaceholder', '描述你的图示，或从下方选择具体图示模板...')
            "
            maxlength="50"
            @keydown.enter="handleFreeInput"
          />
          <button
            class="absolute right-2 top-1/2 -translate-y-1/2 flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-600 text-white active:bg-indigo-700 transition-colors disabled:opacity-40"
            :disabled="!uiStore.freeInputValue?.trim()"
            @click="handleFreeInput"
          >
            <ArrowRight :size="18" />
          </button>
        </div>

        <!-- Section title -->
        <div class="text-sm font-semibold text-gray-500 mb-3">
          {{ t('landing.diagramGrid.sectionTitle') }}
        </div>

        <!-- Diagram type grid — 2 columns -->
        <div class="grid grid-cols-3 gap-3">
          <button
            v-for="item in diagramTypes"
            :key="item.type"
            class="diagram-card flex flex-col items-center p-4 bg-white rounded-xl border border-gray-200 active:border-indigo-400 active:bg-indigo-50/30 transition-all text-center"
            @click="handleSelectType(item)"
          >
            <div class="w-full min-h-[48px] flex items-center justify-center mb-2">
              <DiagramPreviewSvg :type="item.type" />
            </div>
            <div class="text-sm font-medium text-gray-800 leading-snug">
              {{ t(item.titleKey) }}
            </div>
            <div class="text-xs text-gray-500 leading-snug mt-0.5">
              {{ t(item.descKey) }}
            </div>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mobile-mg-header {
  -webkit-user-select: none;
  user-select: none;
  z-index: 10;
}

.diagram-card {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.diagram-card:active {
  transform: scale(0.97);
}
</style>

<style>
.el-drawer.diagram-history-drawer {
  width: 80vw !important;
  max-width: 320px !important;
  background: #ffffff !important;
}

.el-drawer.diagram-history-drawer .el-drawer__header {
  padding: 16px !important;
  margin-bottom: 0 !important;
  border-bottom: 1px solid #e5e7eb !important;
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
}

.el-drawer.diagram-history-drawer .el-drawer__header span {
  font-size: 16px !important;
  font-weight: 600 !important;
  color: #1f2937 !important;
}

.el-drawer.diagram-history-drawer .el-drawer__header .el-drawer__close-btn {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  order: 1 !important;
  width: 32px !important;
  height: 32px !important;
  padding: 0 !important;
  border-radius: 8px !important;
  margin: 0 !important;
}

.el-drawer.diagram-history-drawer .el-drawer__body {
  padding: 8px 12px !important;
  background: #ffffff !important;
}

.el-drawer.diagram-history-drawer .diagram-type {
  display: none !important;
}

.el-drawer.diagram-history-drawer .diagram-info {
  gap: 0 !important;
}

.el-drawer.diagram-history-drawer .delete-btn {
  opacity: 0.6 !important;
}

.el-drawer.diagram-history-drawer .diagram-history > .px-4.py-3 {
  display: none !important;
}
</style>
