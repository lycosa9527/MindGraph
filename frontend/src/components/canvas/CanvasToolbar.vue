<script setup lang="ts">
/**
 * CanvasToolbar - Floating toolbar for canvas editing
 * Migrated from prototype MindGraphCanvasPage toolbar
 */
import { ref } from 'vue'

import { ElButton, ElDropdown, ElDropdownItem, ElDropdownMenu, ElMessage, ElTooltip } from 'element-plus'

import {
  Brush,
  ChevronDown,
  Fish,
  Image as ImageIcon,
  LayoutGrid,
  Package,
  PenLine,
  Plus,
  RotateCcw,
  RotateCw,
  Square,
  Trash2,
  Type,
  Wand2,
} from 'lucide-vue-next'

import { useLanguage } from '@/composables'

const { isZh } = useLanguage()

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
    icon: LayoutGrid,
    desc: '在批量节点中选择，发散聚合思维显性化',
    tag: '热门',
    iconBg: 'bg-blue-100',
    iconColor: 'text-blue-600',
  },
  {
    name: '半成品图示',
    icon: Package,
    desc: '随机留空，学习复习好搭子',
    iconBg: 'bg-purple-100',
    iconColor: 'text-purple-600',
  },
  {
    name: '专家鱼骨图',
    icon: Fish,
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
  const diagramType = diagramStore.type
  
  if (!diagramStore.data?.nodes) {
    ElMessage.warning('请先创建图示')
    return
  }

  // For circle maps, add a new context node
  if (diagramType === 'circle_map') {
    // Find existing context nodes to determine next index
    const contextNodes = diagramStore.data.nodes.filter(
      (n) => n.type === 'bubble' && n.id.startsWith('context-')
    )
    const newIndex = contextNodes.length
    
    // Add new context node (layout will be recalculated automatically)
    diagramStore.addNode({
      id: `context-${newIndex}`,
      text: '新联想',
      type: 'bubble',
      position: { x: 0, y: 0 }, // Will be recalculated
    })
    
    diagramStore.pushHistory('添加节点')
    ElMessage.success('已添加新节点')
    return
  }

  // For other diagram types, show under development message
  ElMessage.info('增加节点功能开发中')
}

function handleDeleteNode() {
  const diagramType = diagramStore.type
  
  if (!diagramStore.data?.nodes) {
    ElMessage.warning('请先创建图示')
    return
  }

  // Check if any nodes are selected
  if (diagramStore.selectedNodes.length === 0) {
    ElMessage.warning('请先选择要删除的节点')
    return
  }

  // For circle maps, delete selected context nodes
  if (diagramType === 'circle_map') {
    let deletedCount = 0
    
    // Delete each selected node (skip topic/boundary)
    for (const nodeId of diagramStore.selectedNodes) {
      if (nodeId.startsWith('context-')) {
        if (diagramStore.removeNode(nodeId)) {
          deletedCount++
        }
      }
    }
    
    if (deletedCount > 0) {
      // Re-index remaining context nodes
      const contextNodes = diagramStore.data.nodes.filter(
        (n) => n.type === 'bubble' && n.id.startsWith('context-')
      )
      contextNodes.forEach((node, index) => {
        node.id = `context-${index}`
      })
      
      diagramStore.clearSelection()
      diagramStore.pushHistory('删除节点')
      ElMessage.success(`已删除 ${deletedCount} 个节点`)
    } else {
      ElMessage.warning('无法删除主题节点')
    }
    return
  }

  // For other diagram types, show under development message
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
  <div class="canvas-toolbar absolute top-[60px] left-1/2 transform -translate-x-1/2 z-10">
    <div
      class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 border-t-0 rounded-b-xl shadow-lg p-1.5 flex items-center justify-center"
    >
      <div class="toolbar-content flex items-center bg-gray-50 dark:bg-gray-700/50 rounded-lg p-1 gap-0.5">
        <!-- Undo/Redo -->
        <ElTooltip :content="isZh ? '撤销' : 'Undo'" placement="bottom">
          <ElButton text size="small" @click="handleUndo">
            <RotateCw class="w-4 h-4" />
          </ElButton>
        </ElTooltip>
        <ElTooltip :content="isZh ? '重做' : 'Redo'" placement="bottom">
          <ElButton text size="small" @click="handleRedo">
            <RotateCcw class="w-4 h-4" />
          </ElButton>
        </ElTooltip>

        <div class="divider" />

        <!-- Add/Delete node -->
        <ElTooltip :content="isZh ? '增加节点' : 'Add Node'" placement="bottom">
          <ElButton text size="small" @click="handleAddNode">
            <Plus class="w-4 h-4" />
            <span>{{ isZh ? '增加节点' : 'Add' }}</span>
          </ElButton>
        </ElTooltip>
        <ElTooltip :content="isZh ? '删除节点' : 'Delete Node'" placement="bottom">
          <ElButton text size="small" @click="handleDeleteNode">
            <Trash2 class="w-4 h-4" />
            <span>{{ isZh ? '删除节点' : 'Delete' }}</span>
          </ElButton>
        </ElTooltip>

        <div class="divider" />

        <!-- Format brush -->
        <ElTooltip :content="isZh ? '格式刷' : 'Format Painter'" placement="bottom">
          <ElButton text size="small" @click="handleFormatBrush">
            <PenLine class="w-4 h-4 text-purple-500" />
          </ElButton>
        </ElTooltip>

        <div class="divider" />

        <!-- Style dropdown -->
        <ElDropdown trigger="hover" placement="bottom">
          <ElButton text size="small">
            <Brush class="w-4 h-4" />
            <span>{{ isZh ? '风格' : 'Style' }}</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <div class="p-3 w-48">
                <div class="text-xs font-medium text-gray-500 mb-2">{{ isZh ? '预设样式' : 'Presets' }}</div>
                <div class="grid grid-cols-2 gap-2">
                  <ElDropdownItem
                    v-for="preset in stylePresets"
                    :key="preset.name"
                    class="!p-2 rounded border text-xs text-center"
                    :class="[preset.bgClass, preset.borderClass]"
                  >
                    {{ preset.name }}
                  </ElDropdownItem>
                </div>
                <div class="border-t border-gray-200 my-2" />
                <ElDropdownItem>
                  <PenLine class="w-3 h-3 mr-2 text-gray-500" />
                  {{ isZh ? '线稿模式' : 'Wireframe' }}
                </ElDropdownItem>
              </div>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <!-- Text style dropdown -->
        <ElDropdown trigger="hover" placement="bottom">
          <ElButton text size="small">
            <Type class="w-4 h-4" />
            <span>{{ isZh ? '文本样式' : 'Text' }}</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <div class="p-3 w-56">
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1">{{ isZh ? '字体' : 'Font' }}:</label>
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
                  <label class="text-xs text-gray-500 block mb-1">{{ isZh ? '字号' : 'Size' }}:</label>
                  <input
                    v-model.number="fontSize"
                    type="number"
                    class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1">{{ isZh ? '颜色' : 'Color' }}:</label>
                  <div
                    class="w-10 h-10 border border-gray-300 rounded-md cursor-pointer"
                    :style="{ backgroundColor: textColor }"
                  />
                </div>
                <div class="flex gap-2 mt-2">
                  <button class="p-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 font-bold">B</button>
                  <button class="p-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 italic">I</button>
                  <button class="p-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 underline">U</button>
                  <button class="p-1.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-100 line-through">S</button>
                </div>
              </div>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <!-- Background dropdown -->
        <ElDropdown trigger="hover" placement="bottom">
          <ElButton text size="small">
            <ImageIcon class="w-4 h-4" />
            <span>{{ isZh ? '背景' : 'BG' }}</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <div class="p-3 w-56">
                <div class="mb-3">
                  <label class="text-xs text-gray-500 block mb-1">{{ isZh ? '背景颜色' : 'Background Color' }}:</label>
                  <div class="grid grid-cols-5 gap-1">
                    <div
                      v-for="color in backgroundColors"
                      :key="color"
                      class="w-6 h-6 rounded border border-gray-200 cursor-pointer hover:ring-2 hover:ring-blue-400"
                      :style="{ backgroundColor: color }"
                    />
                  </div>
                </div>
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1">{{ isZh ? '透明度' : 'Opacity' }}:</label>
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
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <!-- Border dropdown -->
        <ElDropdown trigger="hover" placement="bottom">
          <ElButton text size="small">
            <Square class="w-4 h-4" />
            <span>{{ isZh ? '边框' : 'Border' }}</span>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <div class="p-3 w-56">
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1">{{ isZh ? '颜色' : 'Color' }}:</label>
                  <div
                    class="w-10 h-10 border border-gray-300 rounded-md cursor-pointer"
                    :style="{ backgroundColor: borderColor }"
                  />
                </div>
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1">{{ isZh ? '粗细' : 'Width' }}:</label>
                  <input
                    v-model.number="borderWidth"
                    type="number"
                    class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div class="mb-2">
                  <label class="text-xs text-gray-500 block mb-1">{{ isZh ? '样式' : 'Style' }}:</label>
                  <select
                    v-model="borderStyle"
                    class="w-full border border-gray-300 rounded-md py-1.5 px-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="solid">{{ isZh ? '实线' : 'Solid' }}</option>
                    <option value="dashed">{{ isZh ? '虚线' : 'Dashed' }}</option>
                    <option value="dotted">{{ isZh ? '点线' : 'Dotted' }}</option>
                  </select>
                </div>
              </div>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <div class="divider" />

        <!-- AI Generate button -->
        <ElButton
          type="primary"
          size="small"
          class="ai-btn"
          @click="handleAIGenerate"
        >
          <Wand2 class="w-4 h-4" />
          <span>{{ isZh ? 'AI生成图示' : 'AI Generate' }}</span>
        </ElButton>

        <!-- More apps dropdown -->
        <ElDropdown trigger="hover" placement="bottom-end">
          <ElButton size="small" class="more-apps-btn">
            <span>{{ isZh ? '更多应用' : 'More Apps' }}</span>
            <ChevronDown class="w-3.5 h-3.5" />
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu class="more-apps-menu">
              <ElDropdownItem
                v-for="app in moreApps"
                :key="app.name"
                @click="handleMoreApp(app.name)"
              >
                <div class="flex items-start py-1">
                  <div class="rounded-full p-2 mr-3 flex-shrink-0" :class="app.iconBg">
                    <component :is="app.icon" class="w-4 h-4" :class="app.iconColor" />
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="font-medium mb-0.5 flex items-center">
                      {{ app.name }}
                      <span
                        v-if="app.tag"
                        class="ml-2 text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded-full"
                      >{{ app.tag }}</span>
                    </div>
                    <div class="text-xs text-gray-500">{{ app.desc }}</div>
                  </div>
                </div>
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Divider between button groups */
.divider {
  height: 20px;
  width: 1px;
  background-color: #d1d5db;
  margin: 0 6px;
}

/* Ensure toolbar doesn't wrap */
.toolbar-content {
  flex-wrap: nowrap;
  white-space: nowrap;
}

/* Reset Element Plus button styles to match prototype exactly */
/* Prototype uses: p-2 rounded hover:bg-gray-200 transition-colors */
:deep(.toolbar-content .el-button) {
  --el-button-hover-bg-color: transparent;
  --el-button-hover-text-color: inherit;
  padding: 8px !important; /* p-2 = 8px */
  margin: 0 !important;
  min-height: auto !important;
  height: auto !important;
  border-radius: 4px !important; /* rounded = 4px */
  transition: all 0.15s ease !important;
  border: none !important;
  font-size: 12px !important; /* text-xs = 12px */
}

:deep(.toolbar-content .el-button--text) {
  color: #4b5563 !important; /* gray-600 */
  background: transparent !important;
}

:deep(.toolbar-content .el-button--text:hover) {
  background-color: #d1d5db !important; /* gray-300 for visibility */
  color: #374151 !important; /* gray-700 */
}

:deep(.toolbar-content .el-button--text:active) {
  background-color: #9ca3af !important; /* gray-400 */
}

:deep(.toolbar-content .el-button--text span) {
  margin-left: 0 !important;
}

/* Icon-only buttons should be square */
:deep(.toolbar-content .el-button--text:not(:has(span))) {
  padding: 8px !important;
}

/* Buttons with text: icon + gap-1 + text */
:deep(.toolbar-content .el-button:has(span)) {
  display: inline-flex !important;
  align-items: center !important;
  gap: 4px !important; /* gap-1 = 4px */
}

/* Dark mode text buttons */
:deep(.dark .toolbar-content .el-button--text) {
  color: #d1d5db !important; /* gray-300 */
}

:deep(.dark .toolbar-content .el-button--text:hover) {
  background-color: #4b5563 !important; /* gray-600 */
  color: #f3f4f6 !important; /* gray-100 */
}

:deep(.dark .toolbar-content .el-button--text:active) {
  background-color: #374151 !important; /* gray-700 */
}

/* AI Generate button styling */
:deep(.ai-btn) {
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
  border: none !important;
  padding: 6px 16px !important;
  margin-left: 8px !important;
  gap: 6px !important;
}

:deep(.ai-btn:hover) {
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
}

:deep(.ai-btn span) {
  color: white !important;
}

/* More apps button styling */
:deep(.more-apps-btn) {
  background: white !important;
  border: 1px solid #e5e7eb !important;
  color: #374151 !important;
  padding: 6px 12px !important;
  margin-left: 8px !important;
  gap: 4px !important;
}

:deep(.more-apps-btn:hover) {
  background: #f9fafb !important;
  border-color: #d1d5db !important;
}

:deep(.more-apps-btn span) {
  color: #374151 !important;
}

/* More apps dropdown menu */
:deep(.more-apps-menu) {
  width: 280px !important;
}

:deep(.more-apps-menu .el-dropdown-menu__item) {
  padding: 8px 12px !important;
  line-height: 1.4 !important;
}

/* Dark mode support */
:deep(.dark) .divider {
  background-color: #4b5563;
}

:deep(.dark) .more-apps-btn {
  background: #374151 !important;
  border-color: #4b5563 !important;
  color: #e5e7eb !important;
}
</style>
