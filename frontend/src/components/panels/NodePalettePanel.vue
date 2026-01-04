<script setup lang="ts">
/**
 * Node Palette Panel - Node type selector with drag-and-drop
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables'
import { useDiagramStore } from '@/stores'
import type { NodeType } from '@/types'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const diagramStore = useDiagramStore()
const { isZh } = useLanguage()

// Node categories
interface NodeTemplate {
  type: NodeType
  nameEn: string
  nameZh: string
  color: string
  icon: string
}

const nodeCategories = computed(() => [
  {
    name: isZh.value ? '基础节点' : 'Basic Nodes',
    nodes: [
      {
        type: 'topic' as NodeType,
        nameEn: 'Topic',
        nameZh: '主题',
        color: '#409eff',
        icon: 'Star',
      },
      {
        type: 'child' as NodeType,
        nameEn: 'Child',
        nameZh: '子节点',
        color: '#67c23a',
        icon: 'Document',
      },
      {
        type: 'branch' as NodeType,
        nameEn: 'Branch',
        nameZh: '分支',
        color: '#e6a23c',
        icon: 'Connection',
      },
    ],
  },
  {
    name: isZh.value ? '气泡图节点' : 'Bubble Nodes',
    nodes: [
      {
        type: 'center' as NodeType,
        nameEn: 'Center',
        nameZh: '中心',
        color: '#f56c6c',
        icon: 'Aim',
      },
      {
        type: 'bubble' as NodeType,
        nameEn: 'Bubble',
        nameZh: '气泡',
        color: '#909399',
        icon: 'CirclePlus',
      },
    ],
  },
  {
    name: isZh.value ? '流程图节点' : 'Flow Nodes',
    nodes: [
      { type: 'left' as NodeType, nameEn: 'Cause', nameZh: '原因', color: '#b88230', icon: 'Back' },
      {
        type: 'right' as NodeType,
        nameEn: 'Effect',
        nameZh: '结果',
        color: '#67c23a',
        icon: 'Right',
      },
    ],
  },
])

// Drag state
const draggedNode = ref<NodeTemplate | null>(null)

function handleDragStart(event: DragEvent, node: NodeTemplate) {
  draggedNode.value = node
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'copy'
    event.dataTransfer.setData('application/json', JSON.stringify(node))
  }
}

function handleDragEnd() {
  draggedNode.value = null
}

// Add node on click
function addNode(node: NodeTemplate) {
  const newNode = {
    id: `node-${Date.now()}`,
    text: isZh.value ? node.nameZh : node.nameEn,
    type: node.type,
    position: { x: 400, y: 300 }, // Center of canvas
    style: {
      backgroundColor: '#ffffff',
      borderColor: node.color,
      textColor: '#303133',
    },
  }

  diagramStore.pushHistory('Add node')
  diagramStore.addNode(newNode)
}
</script>

<template>
  <div
    class="node-palette-panel bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 shadow-lg flex flex-col"
  >
    <!-- Header -->
    <div
      class="panel-header h-12 px-4 flex items-center justify-between border-b border-gray-200 dark:border-gray-700"
    >
      <h3 class="font-medium text-gray-800 dark:text-white">
        {{ isZh ? '节点面板' : 'Node Palette' }}
      </h3>
      <el-button
        text
        circle
        @click="emit('close')"
      >
        <el-icon><Close /></el-icon>
      </el-button>
    </div>

    <!-- Content -->
    <div class="panel-content flex-1 overflow-y-auto p-4">
      <div
        v-for="category in nodeCategories"
        :key="category.name"
        class="category mb-6"
      >
        <h4
          class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3"
        >
          {{ category.name }}
        </h4>

        <div class="grid grid-cols-2 gap-2">
          <div
            v-for="node in category.nodes"
            :key="node.type"
            class="node-item p-3 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-600 hover:border-primary-400 dark:hover:border-primary-500 cursor-grab transition-colors"
            draggable="true"
            @dragstart="handleDragStart($event, node)"
            @dragend="handleDragEnd"
            @click="addNode(node)"
          >
            <div class="flex items-center gap-2">
              <div
                class="w-6 h-6 rounded flex items-center justify-center"
                :style="{ backgroundColor: node.color + '20', color: node.color }"
              >
                <el-icon :size="14">
                  <component :is="node.icon" />
                </el-icon>
              </div>
              <span class="text-sm text-gray-700 dark:text-gray-300">
                {{ isZh ? node.nameZh : node.nameEn }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Help text -->
      <div class="mt-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
        <p class="text-xs text-gray-500 dark:text-gray-400">
          {{
            isZh
              ? '点击添加节点到画布中心，或拖拽到指定位置。'
              : 'Click to add node to canvas center, or drag to a specific location.'
          }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.node-palette-panel {
  height: 100%;
}

.node-item:active {
  cursor: grabbing;
}

.node-item:hover {
  background-color: rgba(64, 158, 255, 0.05);
}
</style>
