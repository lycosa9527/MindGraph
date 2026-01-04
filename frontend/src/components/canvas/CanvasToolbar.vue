<script setup lang="ts">
/**
 * CanvasToolbar - Floating toolbar for canvas editing
 * Migrated from prototype MindGraphCanvasPage toolbar
 */
import { ref } from 'vue'

import { ElMessage } from 'element-plus'

import {
  Brush,
  ChevronDown,
  Image as ImageIcon,
  PenLine,
  Plus,
  RotateCcw,
  RotateCw,
  Square,
  Trash2,
  Type,
  Wand2,
} from 'lucide-vue-next'

import { useDiagramStore } from '@/stores'

const diagramStore = useDiagramStore()

// Dropdown visibility (prefixed with _ to indicate intentionally unused - reserved for future)
const _showStyleDropdown = ref(false)
const _showTextDropdown = ref(false)
const _showBackgroundDropdown = ref(false)
const _showBorderDropdown = ref(false)
const _showMoreAppsDropdown = ref(false)

// Text style state
const fontFamily = ref('Arial')
const fontSize = ref(16)
const textColor = ref('#000000')

// Background state
const backgroundColors = ['#FFFFFF', '#F9FAFB', '#F3F4F6', '#E5E7EB', '#D1D5DB']
const backgroundOpacity = ref(100)

// Border state
const borderColor = ref('#000000')
const borderWidth = ref(1)
const borderStyle = ref('solid')

// Style presets
const stylePresets = [
  { name: '简约风格', bgClass: 'bg-blue-50', borderClass: 'border-blue-200' },
  { name: '创意风格', bgClass: 'bg-purple-50', borderClass: 'border-purple-200' },
  { name: '商务风格', bgClass: 'bg-green-50', borderClass: 'border-green-200' },
  { name: '活力风格', bgClass: 'bg-yellow-50', borderClass: 'border-yellow-200' },
]

// More apps items
const moreApps = [
  {
    name: '瀑布流',
    icon: 'grid',
    desc: '在批量节点中选择，发散聚合思维显性化',
    tag: '热门',
    iconBg: 'bg-blue-100',
    iconColor: 'text-blue-600',
  },
  {
    name: '半成品图示',
    icon: 'box',
    desc: '随机留空，学习复习好搭子',
    iconBg: 'bg-purple-100',
    iconColor: 'text-purple-600',
  },
  {
    name: '专家鱼骨图',
    icon: 'fish',
    desc: '问题分析与原因追溯工具',
    iconBg: 'bg-green-100',
    iconColor: 'text-green-600',
  },
]

function handleUndo() {
  diagramStore.undo()
}

function handleRedo() {
  diagramStore.redo()
}

function handleAddNode() {
  ElMessage.info('增加节点功能开发中')
}

function handleDeleteNode() {
  ElMessage.info('删除节点功能开发中')
}

function handleFormatBrush() {
  ElMessage.info('格式刷功能开发中')
}

function handleAIGenerate() {
  ElMessage.info('AI生成图示功能开发中')
}

function handleMoreApp(appName: string) {
  ElMessage.info(`${appName}功能开发中`)
}
</script>

<template>
  <div class="canvas-toolbar absolute top-[60px] left-1/2 transform -translate-x-1/2 w-[65%] z-10">
    <div
      class="bg-white border border-gray-200 border-t-0 rounded-b-lg shadow-md p-1 flex items-center justify-center"
    >
      <div class="flex items-center bg-gray-50 rounded-lg p-1">
        <!-- Undo/Redo -->
        <button
          class="p-2 rounded hover:bg-gray-200 transition-colors"
          title="撤销"
          @click="handleUndo"
        >
          <RotateCw class="w-4 h-4 text-gray-600" />
        </button>
        <button
          class="p-2 rounded hover:bg-gray-200 transition-colors"
          title="重做"
          @click="handleRedo"
        >
          <RotateCcw class="w-4 h-4 text-gray-600" />
        </button>

        <div class="h-5 border-r border-gray-200 mx-1" />

        <!-- Add/Delete node -->
        <button
          class="p-2 rounded hover:bg-gray-200 transition-colors flex items-center gap-1"
          title="增加节点"
          @click="handleAddNode"
        >
          <Plus class="w-4 h-4 text-gray-600" />
          <span class="text-xs text-gray-700">增加节点</span>
        </button>
        <button
          class="p-2 rounded hover:bg-gray-200 transition-colors flex items-center gap-1"
          title="删除节点"
          @click="handleDeleteNode"
        >
          <Trash2 class="w-4 h-4 text-gray-600" />
          <span class="text-xs text-gray-700">删除节点</span>
        </button>

        <div class="h-5 border-r border-gray-200 mx-1" />

        <!-- Format brush -->
        <button
          class="p-2 rounded hover:bg-gray-200 transition-colors"
          title="格式刷"
          @click="handleFormatBrush"
        >
          <PenLine class="w-4 h-4 text-purple-500" />
        </button>

        <div class="h-5 border-r border-gray-200 mx-1" />

        <!-- Style dropdown -->
        <div class="relative group">
          <button
            class="p-2 rounded hover:bg-gray-200 transition-colors flex items-center gap-1"
            title="风格"
          >
            <Brush class="w-4 h-4 text-gray-600" />
            <span class="text-xs text-gray-700">风格</span>
          </button>
          <div
            class="absolute left-0 top-full mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-20 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200"
          >
            <div class="p-2">
              <div class="text-xs font-medium text-gray-500 mb-2">预设样式</div>
              <div class="grid grid-cols-2 gap-2">
                <div
                  v-for="preset in stylePresets"
                  :key="preset.name"
                  class="p-2 rounded border text-xs text-center cursor-pointer transition-colors"
                  :class="[
                    preset.bgClass,
                    preset.borderClass,
                    `hover:${preset.bgClass.replace('50', '100')}`,
                  ]"
                >
                  {{ preset.name }}
                </div>
              </div>
              <div class="border-t border-gray-200 my-2" />
              <button
                class="w-full text-left px-2 py-2 text-xs text-gray-700 hover:bg-gray-100 transition-colors flex items-center"
              >
                <PenLine class="w-3 h-3 mr-2 text-gray-500" />
                线稿模式
              </button>
            </div>
          </div>
        </div>

        <!-- Text style dropdown -->
        <div class="relative group">
          <button
            class="p-2 rounded hover:bg-gray-200 transition-colors flex items-center gap-1"
            title="文本样式"
          >
            <Type class="w-4 h-4 text-gray-600" />
            <span class="text-xs text-gray-700">文本样式</span>
          </button>
          <div
            class="absolute left-0 top-full mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg z-20 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200"
          >
            <div class="p-3">
              <div class="mb-2">
                <label class="text-xs text-gray-500 block mb-1">字体:</label>
                <select
                  v-model="fontFamily"
                  class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="Arial">Arial</option>
                  <option value="Microsoft YaHei">微软雅黑</option>
                  <option value="SimSun">宋体</option>
                  <option value="SimHei">黑体</option>
                </select>
              </div>
              <div class="mb-2">
                <label class="text-xs text-gray-500 block mb-1">字号:</label>
                <input
                  v-model.number="fontSize"
                  type="number"
                  class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div class="mb-2">
                <label class="text-xs text-gray-500 block mb-1">颜色:</label>
                <div
                  class="w-10 h-10 border border-gray-300 rounded-md cursor-pointer"
                  :style="{ backgroundColor: textColor }"
                />
              </div>
              <div class="flex gap-2 mt-2">
                <button
                  class="p-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 transition-colors font-bold"
                >
                  B
                </button>
                <button
                  class="p-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 transition-colors italic"
                >
                  I
                </button>
                <button
                  class="p-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 transition-colors underline"
                >
                  U
                </button>
                <button
                  class="p-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 transition-colors line-through"
                >
                  S
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Background dropdown -->
        <div class="relative group">
          <button
            class="p-2 rounded hover:bg-gray-200 transition-colors flex items-center gap-1"
            title="背景"
          >
            <ImageIcon class="w-4 h-4 text-gray-600" />
            <span class="text-xs text-gray-700">背景</span>
          </button>
          <div
            class="absolute left-0 top-full mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg z-20 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200"
          >
            <div class="p-3">
              <div class="mb-3">
                <label class="text-xs text-gray-500 block mb-1">背景颜色:</label>
                <div class="grid grid-cols-5 gap-1">
                  <div
                    v-for="color in backgroundColors"
                    :key="color"
                    class="w-6 h-6 rounded border border-gray-200 cursor-pointer"
                    :style="{ backgroundColor: color }"
                  />
                </div>
              </div>
              <div class="mb-2">
                <label class="text-xs text-gray-500 block mb-1">透明度:</label>
                <input
                  v-model.number="backgroundOpacity"
                  type="range"
                  min="0"
                  max="100"
                  class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <div class="flex justify-between text-xs text-gray-500 mt-1">
                  <span>0%</span>
                  <span>100%</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Border dropdown -->
        <div class="relative group">
          <button
            class="p-2 rounded hover:bg-gray-200 transition-colors flex items-center gap-1"
            title="边框"
          >
            <Square class="w-4 h-4 text-gray-600" />
            <span class="text-xs text-gray-700">边框</span>
          </button>
          <div
            class="absolute left-0 top-full mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg z-20 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200"
          >
            <div class="p-3">
              <div class="mb-2">
                <label class="text-xs text-gray-500 block mb-1">颜色:</label>
                <div
                  class="w-10 h-10 border border-gray-300 rounded-md cursor-pointer"
                  :style="{ backgroundColor: borderColor }"
                />
              </div>
              <div class="mb-2">
                <label class="text-xs text-gray-500 block mb-1">粗细:</label>
                <input
                  v-model.number="borderWidth"
                  type="number"
                  class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div class="mb-2">
                <label class="text-xs text-gray-500 block mb-1">样式:</label>
                <select
                  v-model="borderStyle"
                  class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="solid">实线</option>
                  <option value="dashed">虚线</option>
                  <option value="dotted">点线</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <div class="h-5 border-r border-gray-200 mx-1" />

        <!-- AI Generate button -->
        <button
          class="px-4 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm font-medium flex items-center gap-1 shadow-md"
          @click="handleAIGenerate"
        >
          <Wand2 class="w-3.5 h-3.5" />
          AI生成图示
        </button>

        <!-- More apps dropdown -->
        <div class="relative group ml-2">
          <button
            class="px-4 py-1.5 bg-white text-gray-700 rounded-md hover:bg-gray-50 transition-colors text-sm font-medium flex items-center gap-1 border border-gray-200 shadow-sm"
          >
            更多应用
            <ChevronDown
              class="w-3.5 h-3.5 text-gray-500 group-hover:rotate-180 transition-transform duration-200"
            />
          </button>
          <div
            class="absolute right-0 top-full mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-20 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 transform translate-y-2 group-hover:translate-y-0"
          >
            <button
              v-for="app in moreApps"
              :key="app.name"
              class="w-full text-left px-4 py-3 text-sm text-gray-800 hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-b-0"
              @click="handleMoreApp(app.name)"
            >
              <div class="flex items-start">
                <div
                  class="rounded-full p-1.5 mr-3 mt-0.5"
                  :class="app.iconBg"
                >
                  <div
                    class="w-4 h-4"
                    :class="app.iconColor"
                  />
                </div>
                <div>
                  <div class="font-medium mb-1 flex items-center">
                    {{ app.name }}
                    <span
                      v-if="app.tag"
                      class="ml-2 text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full"
                      >{{ app.tag }}</span
                    >
                  </div>
                  <div class="text-xs text-gray-500">{{ app.desc }}</div>
                </div>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
