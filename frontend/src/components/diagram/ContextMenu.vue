<script setup lang="ts">
/**
 * ContextMenu - Custom right-click context menu for diagram canvas
 * Replaces browser's default context menu with custom actions
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { eventBus } from '@/composables/useEventBus'
import { useLanguage, useNotifications } from '@/composables'
import {
  BRANCH_NODE_HEIGHT,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
} from '@/composables/diagrams/layoutConfig'
import { useDiagramStore } from '@/stores'
import type { DiagramNode, MindGraphNode } from '@/types'

interface MenuItem {
  label?: string
  icon?: string
  action?: () => void
  disabled?: boolean
  divider?: boolean
}

interface Props {
  visible: boolean
  x: number
  y: number
  node?: MindGraphNode | null
  target?: 'node' | 'pane'
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'paste', position: { x: number; y: number }): void
}>()

const diagramStore = useDiagramStore()
const { isZh } = useLanguage()
const notify = useNotifications()
const menuRef = ref<HTMLElement | null>(null)

// Build menu items based on context
const menuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = []

  if (props.target === 'node' && props.node) {
    const node = props.node
    const nodeData = node.data
    const isTopicNode = nodeData?.nodeType === 'topic'
    const isBoundaryNode = nodeData?.nodeType === 'boundary'

    // Edit action
    items.push({
      label: '编辑',
      action: () => {
        emit('close')
        // Emit event to trigger edit mode
        eventBus.emit('node:edit_requested', { nodeId: node.id })
      },
    })

    items.push({ divider: true })

    // Delete action (disabled for topic/center/boundary nodes)
    items.push({
      label: '删除',
      action: () => {
        if (diagramStore.removeNode(node.id)) {
          diagramStore.pushHistory('删除节点')
          emit('close')
        }
      },
      disabled: isTopicNode || isBoundaryNode,
    })

    items.push({ divider: true })

    // For multi-flow map, add "Add Cause" or "Add Effect" based on node type
    if (diagramStore.type === 'multi_flow_map') {
      if (node.id.startsWith('cause-')) {
        items.push({
          label: '添加原因',
          action: () => {
            diagramStore.addNode({
              id: 'cause-temp',
              text: '新原因',
              type: 'flow',
              position: { x: 0, y: 0 },
              category: 'causes',
            } as DiagramNode & { category?: string })
            diagramStore.pushHistory('添加原因')
            emit('close')
          },
        })
      } else if (node.id.startsWith('effect-')) {
        items.push({
          label: '添加结果',
          action: () => {
            diagramStore.addNode({
              id: 'effect-temp',
              text: '新结果',
              type: 'flow',
              position: { x: 0, y: 0 },
              category: 'effects',
            } as DiagramNode & { category?: string })
            diagramStore.pushHistory('添加结果')
            emit('close')
          },
        })
      }
      
      items.push({ divider: true })
    }

    // Copy action
    items.push({
      label: '复制',
      action: () => {
        diagramStore.copySelectedNodes()
        emit('close')
      },
      disabled: !diagramStore.hasSelection,
    })

    // Paste action
    items.push({
      label: '粘贴',
      action: () => {
        emit('paste', { x: props.x, y: props.y })
        emit('close')
      },
      disabled: !diagramStore.canPaste,
    })
  } else if (props.target === 'pane') {
    // Pane context menu
    const diagramType = diagramStore.type
    if (diagramType === 'multi_flow_map') {
      // Add cause option
      items.push({
        label: '添加原因',
        action: () => {
          diagramStore.addNode({
            id: 'cause-temp',
            text: '新原因',
            type: 'flow',
            position: { x: 0, y: 0 },
            category: 'causes',
          } as DiagramNode & { category?: string })
          diagramStore.pushHistory('添加原因')
          emit('close')
        },
      })
      
      // Add effect option
      items.push({
        label: '添加结果',
        action: () => {
          diagramStore.addNode({
            id: 'effect-temp',
            text: '新结果',
            type: 'flow',
            position: { x: 0, y: 0 },
            category: 'effects',
          } as DiagramNode & { category?: string })
          diagramStore.pushHistory('添加结果')
          emit('close')
        },
      })
    } else if (diagramType === 'bubble_map') {
      items.push({
        label: '添加属性',
        action: () => {
          if (!diagramStore.data?.nodes) {
            notify.warning(isZh.value ? '请先创建图示' : 'Please create a diagram first')
            emit('close')
            return
          }
          const bubbleNodes = diagramStore.data.nodes.filter(
            (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
          )
          const newIndex = bubbleNodes.length
          diagramStore.addNode({
            id: `bubble-${newIndex}`,
            text: isZh.value ? '新属性' : 'New Attribute',
            type: 'bubble',
            position: { x: 0, y: 0 },
          })
          diagramStore.data.connections.push({
            id: `edge-topic-bubble-${newIndex}`,
            source: 'topic',
            target: `bubble-${newIndex}`,
          })
          diagramStore.pushHistory(isZh.value ? '添加属性' : 'Add Attribute')
          emit('close')
        },
      })
    } else if (diagramType === 'circle_map') {
      items.push({
        label: '添加节点',
        action: () => {
          if (!diagramStore.data?.nodes) {
            notify.warning(isZh.value ? '请先创建图示' : 'Please create a diagram first')
            emit('close')
            return
          }
          const contextNodes = diagramStore.data.nodes.filter(
            (n) => n.type === 'bubble' && n.id.startsWith('context-')
          )
          const newIndex = contextNodes.length
          diagramStore.addNode({
            id: `context-${newIndex}`,
            text: isZh.value ? '新联想' : 'New Idea',
            type: 'bubble',
            position: { x: 0, y: 0 },
          })
          diagramStore.pushHistory(isZh.value ? '添加节点' : 'Add node')
          emit('close')
        },
      })
    } else if (diagramType === 'bridge_map') {
      items.push({
        label: '添加节点',
        action: () => {
          if (!diagramStore.data?.nodes) {
            notify.warning(isZh.value ? '请先创建图示' : 'Please create a diagram first')
            emit('close')
            return
          }
          const pairNodes = diagramStore.data.nodes.filter(
            (n) =>
              n.data?.diagramType === 'bridge_map' &&
              n.data?.pairIndex !== undefined &&
              !n.data?.isDimensionLabel
          )
          let maxPairIndex = -1
          pairNodes.forEach((node) => {
            const pairIndex = node.data?.pairIndex
            if (typeof pairIndex === 'number' && pairIndex > maxPairIndex) {
              maxPairIndex = pairIndex
            }
          })
          const newPairIndex = maxPairIndex + 1
          const centerY = DEFAULT_CENTER_Y
          const gapBetweenPairs = 50
          const verticalGap = 5
          const nodeWidth = DEFAULT_NODE_WIDTH
          const nodeHeight = BRANCH_NODE_HEIGHT
          const gapFromLabelRight = 10
          const estimatedLabelWidth = 100
          const startX = DEFAULT_PADDING + estimatedLabelWidth + gapFromLabelRight
          let nextX = startX
          if (pairNodes.length > 0) {
            const rightmostNode = pairNodes.reduce((rightmost, node) => {
              if (!rightmost) return node
              const rightmostX = rightmost.position?.x || 0
              const nodeX = node.position?.x || 0
              return nodeX > rightmostX ? node : rightmost
            })
            const rightmostX = rightmostNode.position?.x || startX
            nextX = rightmostX + nodeWidth + gapBetweenPairs
          }
          const leftNodeY = centerY - verticalGap - nodeHeight
          const rightNodeY = centerY + verticalGap
          const leftNode: DiagramNode = {
            id: `pair-${newPairIndex}-left`,
            text: isZh.value ? '新事物A' : 'New Item A',
            type: 'branch',
            position: { x: nextX, y: leftNodeY },
            data: {
              pairIndex: newPairIndex,
              position: 'left',
              diagramType: 'bridge_map',
            },
          }
          const rightNode: DiagramNode = {
            id: `pair-${newPairIndex}-right`,
            text: isZh.value ? '新事物B' : 'New Item B',
            type: 'branch',
            position: { x: nextX, y: rightNodeY },
            data: {
              pairIndex: newPairIndex,
              position: 'right',
              diagramType: 'bridge_map',
            },
          }
          diagramStore.addNode(leftNode)
          diagramStore.addNode(rightNode)
          diagramStore.pushHistory(isZh.value ? '添加类比对' : 'Add Analogy Pair')
          emit('close')
        },
      })
    } else {
      items.push({
        label: '添加节点',
        action: () => {
          notify.info(isZh.value ? '增加节点功能开发中' : 'Add node feature coming soon')
          emit('close')
        },
      })
    }

    items.push({ divider: true })

    items.push({
      label: '粘贴',
      action: () => {
        emit('paste', { x: props.x, y: props.y })
        emit('close')
      },
      disabled: !diagramStore.canPaste,
    })
  }

  return items.filter((item) => !item.divider || items.indexOf(item) < items.length - 1)
})

// Close menu when clicking outside
function handleClickOutside(event: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(event.target as Node)) {
    emit('close')
  }
}

// Close menu on Escape key
function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    emit('close')
  }
}

// Position menu to stay within viewport
const menuStyle = computed(() => {
  if (!menuRef.value) {
    return {
      left: `${props.x}px`,
      top: `${props.y}px`,
    }
  }

  const rect = menuRef.value.getBoundingClientRect()
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight

  let left = props.x
  let top = props.y

  // Adjust if menu would overflow right edge
  if (left + rect.width > viewportWidth) {
    left = viewportWidth - rect.width - 10
  }

  // Adjust if menu would overflow bottom edge
  if (top + rect.height > viewportHeight) {
    top = viewportHeight - rect.height - 10
  }

  // Ensure menu doesn't go off left or top edges
  left = Math.max(10, left)
  top = Math.max(10, top)

  return {
    left: `${left}px`,
    top: `${top}px`,
  }
})

function addOutsideListeners(): void {
  document.addEventListener('mousedown', handleClickOutside, true)
  document.addEventListener('keydown', handleKeyDown)
  document.addEventListener('contextmenu', preventDefault)
}

function removeOutsideListeners(): void {
  document.removeEventListener('mousedown', handleClickOutside, true)
  document.removeEventListener('keydown', handleKeyDown)
  document.removeEventListener('contextmenu', preventDefault)
}

// Add/remove listeners when menu visibility changes (not just on mount)
watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      addOutsideListeners()
    } else {
      removeOutsideListeners()
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  removeOutsideListeners()
})

function preventDefault(event: Event) {
  event.preventDefault()
}

function handleItemClick(item: MenuItem) {
  if (!item.disabled && !item.divider && item.action) {
    item.action()
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="context-menu">
      <div
        v-if="visible"
        ref="menuRef"
        class="context-menu"
        :style="menuStyle"
        @contextmenu.prevent
      >
        <div
          v-for="(item, index) in menuItems"
          :key="index"
          class="context-menu-item"
          :class="{ disabled: item.disabled, divider: item.divider }"
          @click="handleItemClick(item)"
        >
          <span v-if="!item.divider && item.label" class="context-menu-label">{{ item.label }}</span>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.context-menu {
  position: fixed;
  z-index: 10000;
  min-width: 160px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 4px 0;
  font-size: 14px;
  user-select: none;
}

.dark .context-menu {
  background: #1f2937;
  border-color: #374151;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.context-menu-item {
  padding: 8px 16px;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.context-menu-item:hover:not(.disabled):not(.divider) {
  background-color: #f3f4f6;
}

.dark .context-menu-item:hover:not(.disabled):not(.divider) {
  background-color: #374151;
}

.context-menu-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.context-menu-item.divider {
  height: 1px;
  padding: 0;
  margin: 4px 0;
  background-color: #e5e7eb;
  cursor: default;
}

.dark .context-menu-item.divider {
  background-color: #374151;
}

.context-menu-label {
  display: block;
  color: #374151;
}

.dark .context-menu-label {
  color: #d1d5db;
}

/* Transition animations */
.context-menu-enter-active,
.context-menu-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.context-menu-enter-from {
  opacity: 0;
  transform: scale(0.95);
}

.context-menu-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
